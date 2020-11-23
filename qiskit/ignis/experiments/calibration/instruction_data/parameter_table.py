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

"""Local database components.

# TODO add detailed description of databases.
"""

from typing import Dict, Union, Iterable, Optional, List, Tuple

import pandas as pd

from qiskit import circuit
from qiskit.ignis.experiments.calibration import types
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.ignis.experiments.calibration.instruction_data import utils


class PulseParameterTable:
    """A database to store parameters of pulses.

    Each entry of this database represents a single parameter associated with the specific pulse,
    and the pulse template is stored in another relational database.

    You can search for the specific entry by filtering or you can directly generate
    keyword argument for the target pulse factory.
    """
    TABLE_COLS = ['qubits', 'channel', 'pulse_name', 'series', 'gate_id',
                  'name', 'value', 'validation', 'timestamp', 'exp_id']

    def __init__(self,
                 channel_qubit_map: Dict[str, Tuple[int]],
                 params_collection: Optional[pd.DataFrame] = None):
        """Create new table.

        Args:
            channel_qubit_map: A map from channel string to qubit index.
            params_collection: Pandas DataFrame object for pulse parameters.
        """
        if params_collection is not None:
            init_dataframe = params_collection
        else:
            init_dataframe = pd.DataFrame(index=[], columns=PulseParameterTable.TABLE_COLS)

        self._parameter_collection = init_dataframe
        self._channel_qubit_map = channel_qubit_map

    def filter_data(
            self,
            qubits: Optional[Union[int, Iterable[int]]] = None,
            channel: Optional[str] = None,
            pulse_name: Optional[str] = None,
            series: Optional[str] = None,
            gate_id: Optional[str] = None,
            name: Optional[str] = None,
            validation: Optional[str] = None
    ) -> pd.DataFrame:
        """Get raw pandas dataframe of waveform parameters.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for. Wildcards can be accepted.
            pulse_name: Name of pulse that parameters belong to.
            series: Name of data set.
            gate_id: Unique id of gate that the pulse belongs to.
            name: Name of parameter to search for. Wildcards can be accepted.
            validation: Status of calibration data validation.

        Returns:
            Pandas dataframe of matched parameters.
        """
        return self._find_data(
            qubits=qubits,
            channel=channel,
            pulse_name=pulse_name,
            series=series,
            gate_id=gate_id,
            name=name,
            validation=validation)

    def get_parameter(
            self,
            parameter: Union[str, circuit.Parameter],
            gate_id: str,
            series: Optional[str] = 'default'
    ) -> Union[int, float, None]:
        """Get waveform parameter from the local database.

        User need to specify parameter object or scoped parameter name
        along with gate_id and series. Those information is sufficient to identify
        unique parameter entry from the parameter collection.

        If there is no matched object or no valid parameter, this returns None
        instead of parameter value.

        Args:
            parameter: Parameter object or scoped parameter name to get.
            gate_id: Target gate id string that the pulse belongs to.
            series: Calibration data set name if multiple sets exist.

        Returns:
            A value corresponding to the input parameter.
        """
        if not isinstance(parameter, str):
            parameter = parameter.name

        scope = utils.remove_scope(parameter)

        matched = self._find_data(**scope, series=series, gate_id=gate_id)

        # filter out invalid entries
        valid_data = matched.query('validation != "{}"'.format(types.Validation.FAIL.value))

        if len(valid_data) == 0:
            return None

        # pick up the latest entry
        df_idx = valid_data['timestamp'].idxmax()
        pval = matched.loc[df_idx].value

        if scope['name'] == 'duration':
            return int(pval)
        else:
            return pval

    def set_parameter(
            self,
            parameter: Union[str, circuit.Parameter],
            gate_id: str,
            value: Union[int, float],
            validation: Optional[str] = None,
            timestamp: Optional[pd.Timestamp] = None,
            exp_id: Optional[str] = None,
            series: Optional[str] = 'default'
    ):
        """Set waveform parameter to the local database.

        Args:
            parameter: Parameter object or scoped parameter name to set.
            gate_id: Target gate id string that the pulse belongs to.
            value: Calibrated parameter value.
            validation: Validation status. Defaults to `None`.
            timestamp: Timestamp of when the value is generated. Defaults to current time.
            exp_id: String representing the id of experiment that calibrated this parameter.
            series: Calibration data set name if multiple sets exist.
        """
        if not isinstance(parameter, str):
            parameter = parameter.name

        scope = utils.remove_scope(parameter)

        # add new data
        self._parameter_collection = self._parameter_collection.append(
            {'qubits': self._channel_qubit_map[scope['channel']],
             'channel': scope['channel'],
             'pulse_name': scope['pulse_name'],
             'series': series,
             'gate_id': gate_id,
             'name': scope['name'],
             'value': value,
             'validation': validation or types.Validation.NONE.value,
             'timestamp': timestamp or pd.Timestamp.now(),
             'exp_id': exp_id
             },
            ignore_index=True
        )

    def set_validation_status(
            self,
            data_index: int,
            status: str
    ):
        """Update validation status of specific pulse table entry.

        Args:
            data_index: Index of pandas data frame.
            status: New status string. `pass`, `fail`, and `none` can be accepted.

        Raises:
            CalExpError: When invalid status string or data index is specified.
        """
        try:
            status = types.Validation(status).value
        except ValueError:
            raise CalExpError('Validation status {status} is not valid string.'
                              ''.format(status=status))

        if data_index > len(self._parameter_collection) - 1:
            raise CalExpError('Data index {index} does not exist'.format(index=data_index))

        self._parameter_collection.at[data_index, 'validation'] = status

    def _find_data(
            self,
            qubits: Optional[Union[int, List[int]]] = None,
            channel: Optional[str] = None,
            pulse_name: Optional[str] = None,
            series: Optional[str] = None,
            gate_id: Optional[str] = None,
            name: Optional[str] = None,
            validation: Optional[str] = None
    ) -> pd.DataFrame:
        """A helper function to return matched dataframe."""
        query_list = []

        # filter by qubits
        if qubits is not None:
            if isinstance(qubits, int):
                qubits = (qubits, )
            query_list.append('qubits == tuple({})'.format(str(qubits)))

        # filter by channel
        if channel:
            query_list.append('channel == "{}"'.format(channel))

        # filter by pulse name
        if pulse_name:
            query_list.append('pulse_name == "{}"'.format(pulse_name))

        # filter by series
        if series:
            query_list.append('series == "{}"'.format(series))

        # filter by gate_id
        if gate_id:
            query_list.append('gate_id == "{}"'.format(gate_id))

        # filter by parameter name
        if name:
            query_list.append('name == "{}"'.format(name))

        # filter by validation status
        if validation:
            query_list.append('validation == "{}"'.format(validation))

        query_str = ' and '.join(query_list)

        if query_str:
            return self._parameter_collection.query(query_str)
        else:
            return self._parameter_collection
