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

from qiskit import pulse, circuit
from qiskit.ignis.experiments.calibration import types


class ParameterTable:
    """A database to store parameters of pulses.

    Each entry of this database represents a single parameter associated with the specific pulse,
    and the pulse template is stored in another database.
    """

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
            parameters: Optional[Union[str, List[str]]] = None,
            use_complex_amplitude: bool = True,
            remove_bad_data: bool = True
    ) -> Dict[str, Union[int, float, complex, circuit.Parameter]]:
        """Get kwargs of calibration parameters to feed into experiment generator.

        Qubit index, channel and gate type should be specified. Wildcards cannot be used.
        This returns only latest calibration data and calibration namespace is removed.
        By default amplitude and phase are converted into complex valued amplitude
        and data entry with bad validation status is not contained in the returned dictionary.

        User can specify a list of parameter names to parametrize.
        If this list is provided, this method returns keyword arguments filled with
        Qiskit parameter object to parametrize calibration schedule.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for.
            gate_type: Name of gate to search for.
            parameters: Name of parameter to parametrize.
                Corresponding calibration data is replaced with Qiskit parameter object.
            use_complex_amplitude: Set `True` to return complex valued amplitude.
                If both ``amp`` and ``phase`` exist in the matched entries,
                this function converts them into single ``amp``.
            remove_bad_data: Set `True` to check validation status of database entry and
                filter out bad calibration data to construct valid keyword arguments.

        Returns:
            Python keyword arguments for experiment generator.
        """
        if parameters is None:
            parameters = []
        elif isinstance(parameters, str):
            parameters = [parameters]

        matched_data = self._find_data(
            qubits=qubits,
            channel=channel,
            gate_type=gate_type
        )
        params_dict = ParameterTable._flatten(matched_data)

        # format dictionary
        format_dict = {}
        for pname, values in params_dict.items():
            reduced_pname = pname.split('.')[-1]
            # parametrize the parameter
            if reduced_pname in parameters:
                format_dict[reduced_pname] = circuit.Parameter(pname)
                continue
            # find database entry with latest timestamp
            if len(values) > 1:
                # filter out bad data
                if remove_bad_data:
                    values = [val for val in values
                              if val.validation != types.ValidationStatus.FAIL.value]
                format_dict[reduced_pname] = sorted(values, key=lambda x: x.timestamp)[-1].value
            else:
                format_dict[reduced_pname] = values[0].value

        # convert (amp, phase) pair into complex value
        if use_complex_amplitude:
            if 'amp' in format_dict and 'phase' in format_dict:
                format_dict['amp'] *= np.exp(1j * format_dict.pop('phase'))

        # convert duration into integer
        if 'duration' in format_dict and isinstance(format_dict['duration'], float):
            format_dict['duration'] = int(format_dict['duration'])

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

        Return the calibration data as parameter value, validation result and timestamp
        assembled in a python NamedTuple.
        Parameter names are unique within the calibration namespace.
        For example, the parameter `amp` associated with qubit 0, channel `d0`
        and `x90p` gate has the unique name `q0.x90p.amp`.

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

    def _find_data(
            self,
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
