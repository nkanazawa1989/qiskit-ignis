# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Data source to generate schedule."""

from typing import Dict, Union, Iterable, Optional, List

import numpy as np
import pandas as pd

from qiskit import pulse
from qiskit.ignis.experiments.calibration import types


class ParameterTable:

    def __init__(self, params_collection: pd.DataFrame):
        self._parameter_collection = params_collection

    def get_dataframe(
            self,
            qubits: Optional[Union[int, Iterable[int]]] = None,
            channel: Optional[str] = None,
            gate_type: Optional[str] = None,
            name: Optional[str] = None,
            validation: Optional[str] = None
    ) -> pd.DataFrame:
        """Get raw pandas dataframe of search results.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for. Wildcards can be accepted.
            gate_type: Name of gate to search for. Wildcards can be accepted.
            name: Name of parameter to search for. Wildcards can be accepted.
            validation: Status of calibration data validation.

        Returns:
            Pandas dataframe of matched parameters.
        """
        return self._find_data(
            qubits=qubits,
            channel=channel,
            gate_type=gate_type,
            name=name,
            validation=validation)

    def get_generator_kwargs(
            self,
            qubits: Union[int, Iterable[int]],
            channel: str,
            gate_type: str,
    ) -> Dict[str, Union[int, float, complex]]:
        """Get kwargs of calibration parameters to feed into experiment generator.

        Qubit index, channel and gate type should be specified. Wildcards cannot be used.
        This returns only latest calibration data and calibration namespace is removed.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for. Wildcards can be accepted.
            gate_type: Name of gate to search for. Wildcards can be accepted.

        Returns:
            Python keyword arguments for experiment generator.
        """
        matched_data = self._find_data(
            qubits=qubits,
            channel=channel,
            gate_type=gate_type
        )
        params_dict = ParameterTable._flatten(matched_data)

        # pick calibrated value with latest time stamp
        format_dict = {}
        for pname, values in params_dict.items():
            reduced_pname = pname.split('.')[-1]
            if len(values) > 1:
                format_dict[reduced_pname] = sorted(values, key=lambda x: x.timestamp)[-1].value
            else:
                format_dict[reduced_pname] = values[0].value

        return format_dict

    def get_cal_data(
            self,
            qubits: Optional[Union[int, Iterable[int]]] = None,
            channel: Optional[str] = None,
            gate_type: Optional[str] = None,
            name: Optional[str] = None,
            validation: Optional[str] = None,
            only_latest: bool = True
            ) -> Dict[str, Union[types.CalValue, List[types.CalValue]]]:
        """Get calibration data from the local database.

        This method returns calibration data consist of value, validation result and timestamp.
        These data are assembled as python NamedTuple.
        Parameter names are converted into unique name with calibration namespace.
        For example, if the parameter `amp` is associated with qubit 0, channel `d0`
        and `x90p` gate, the parameter name becomes `q0.x90p.amp`.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for. Wildcards can be accepted.
            gate_type: Name of gate to search for. Wildcards can be accepted.
            name: Name of parameter to search for. Wildcards can be accepted.
            validation: Status of calibration data validation.
            only_latest: Set `True` to only return single parameter with the latest timestamp.
                If multiple calibration data with different timestamps exist in the
                database, this method returns all of them as a list.

        Returns:
            Python dictionary of formatted calibration data.
        """
        matched_data = self._find_data(
            qubits=qubits,
            channel=channel,
            gate_type=gate_type,
            name=name,
            validation=validation
        )
        params_dict = ParameterTable._flatten(matched_data)

        # pick calibrated value with latest time stamp
        if only_latest:
            for pname, values in params_dict.items():
                if len(values) > 1:
                    params_dict[pname] = sorted(values, key=lambda x: x.timestamp)[-1]
                else:
                    params_dict[pname] = values[0]

        return dict(params_dict)

    def set_cal_data(
            self,
            qubits: Union[int, Iterable[int]],
            channel: str,
            gate_type: str,
            name: str,
            cal_data: Union[int, float, complex, types.CalValue]
    ):
        """Set calibration data to the local database.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for.
            gate_type: Name of gate to search for.
            name: Name of parameter to search for.
            cal_data: Parameter value to update. This can be raw value or `CalValue` instance
                that contains validation status and timestamp.
                If raw value is provided current time is used for the timestamp.
        """
        # prepare data
        if not isinstance(cal_data, types.CalValue):
            cal_data = types.CalValue(
                value=cal_data,
                validation=types.ValidationStatus.NONE.value,
                timestamp=pd.Timestamp.now()
            )
        if isinstance(qubits, int):
            qubits = (qubits,)
        else:
            qubits = tuple(qubits)

        # add new data series
        self._parameter_collection = self._parameter_collection.append(
            {'qubits': qubits,
             'channel': channel,
             'gate_type': gate_type,
             'name': name,
             'value': cal_data.value,
             'validation': cal_data.validation,
             'timestamp': cal_data.timestamp},
            ignore_index=True
        )

    def _find_data(self,
                   qubits: Optional[Union[int, List[int]]] = None,
                   channel: Optional[str] = None,
                   gate_type: Optional[str] = None,
                   name: Optional[str] = None,
                   validation: Optional[str] = None
                   ) -> pd.DataFrame:
        """A helper function to return matched dataframe."""
        flags = []

        # filter by qubit index
        if qubits is not None:
            if isinstance(qubits, int):
                qubits = (qubits,)
            else:
                qubits = tuple(qubits)
            flags.append(self._parameter_collection['qubits'] == qubits)

        # filter by pulse channel
        if channel is not None:
            flags.append(self._parameter_collection['channel'].str.match(channel))

        # filter by gate name
        if gate_type is not None:
            flags.append(self._parameter_collection['gate_type'].str.match(gate_type))

        # filter by parameter name
        if name is not None:
            flags.append(self._parameter_collection['name'].str.match(name))

        # filter by validation
        if validation is not None:
            flags.append(self._parameter_collection['validation'] == validation)

        if flags:
            return self._parameter_collection[np.logical_and.reduce(flags)]
        else:
            return self._parameter_collection

    @classmethod
    def _flatten(cls, entries: pd.DataFrame) -> Dict[str, List[types.CalValue]]:
        """A helper function to convert pandas data series into dictionary."""
        # group duplicated entries
        grouped_params = entries.groupby(['qubits', 'channel', 'gate_type', 'name']).agg({
            'value': tuple,
            'validation': tuple,
            'timestamp': tuple
        })

        flat_dict = {}
        for keys, series in grouped_params.iterrows():
            qind_str = 'q' + '_'.join(map(str, keys[0]))
            pname = '.'.join((qind_str, ) + keys[1:])
            cal_vals = [types.CalValue(val, validation, timestamp) for
                        val, validation, timestamp in
                        zip(series.value, series.validation, series.timestamp)]
            flat_dict[pname] = cal_vals

        return flat_dict


class ScheduleTemplate:

    # TODO: support parametrized schedule, eg Rx(theta) schedule

    def __init__(self, templates: List[Dict[str, Union[str, pulse.Schedule]]]):
        self._templates = templates

    def get_schedule(self,
                     qubits: Union[int, Iterable[int]],
                     name: str,
                     param_table: ParameterTable):
        """"""
        pass
