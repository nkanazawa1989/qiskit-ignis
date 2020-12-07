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

from typing import Dict, Union, Iterable, Optional, List, Tuple, Type

import pandas as pd

from qiskit.ignis.experiments.calibration import types
from qiskit.ignis.experiments.calibration.exceptions import CalExpError

from qiskit.pulse.channels import PulseChannel


class PulseParameterTable:
    """A database to store parameters of pulses.

    Each entry of this database represents a single parameter associated with the specific pulse,
    and the pulse template is stored in another relational database.

    You can search for the specific entry by filtering or you can directly generate
    keyword argument for the target pulse factory.
    """
    TABLE_COLS = ['qubits', 'channel', 'pulse_name', 'calibration_group', 'scope_id',
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

    def get_channel(self, qubits: Tuple,
                    ch_type: Type[PulseChannel]) -> PulseChannel:
        """
        Used to get pulse channels given the qubits and type.

        Args:
            qubits: the index of the qubits for which to get the channel.
            ch_type: type of the pulse channel to return.

        Returns:
            channel: an instance of ch_type for the given qubits and type.
        """
        for key, value in self._channel_qubit_map.items():
            if value == qubits and key[0] == ch_type.prefix:
                return ch_type(int(key[1:]))

        raise KeyError('No channel found for qubits %s.' % (qubits, ))

    def filter_data(
            self,
            qubits: Optional[Union[int, Iterable[int]]] = None,
            channel: Optional[str] = None,
            pulse_name: Optional[str] = None,
            calibration_group: Optional[str] = None,
            scope_id: Optional[str] = None,
            name: Optional[str] = None,
            validation: Optional[str] = None
    ) -> pd.DataFrame:
        """Get raw pandas dataframe of waveform parameters.

        Args:
            qubits: Index of qubit(s) to search for.
            channel: Label of pulse channel to search for. Wildcards can be accepted.
            pulse_name: Name of pulse that parameters belong to.
            calibration_group: Name of data set.
            scope_id: Unique id of gate that the pulse belongs to.
            name: Name of parameter to search for. Wildcards can be accepted.
            validation: Status of calibration data validation.

        Returns:
            Pandas dataframe of matched parameters.
        """
        return self._find_data(
            qubits=qubits,
            channel=channel,
            pulse_name=pulse_name,
            calibration_group=calibration_group,
            scope_id=scope_id,
            name=name,
            validation=validation)

    def get_parameter(
            self,
            parameter_name: str,
            pulse_name: str,
            channel: str,
            scope_id: Optional[str] = 'global',
            calibration_group: Optional[str] = 'default'
    ) -> Union[int, float, str, None]:
        """Get waveform parameter from the local database.

        User need to specify parameter object or scoped parameter name
        along with scope_id and calibration_group.
        Those information is sufficient to identify
        unique parameter entry from the parameter collection.

        If there is no matched object or no valid parameter, this returns None
        instead of parameter value.

        Args:
            parameter_name: Parameter name to get.
            pulse_name: Name of pulse that the parameter is associated with.
            channel: Name of channel where the pulse is played.
            scope_id: Target scope id string that the pulse belongs to.
            calibration_group: Calibration data set name if multiple sets exist.

        Returns:
            A value corresponding to the input parameter.
        """
        matched = self._find_data(name=parameter_name,
                                  pulse_name=pulse_name,
                                  channel=channel,
                                  calibration_group=calibration_group,
                                  scope_id=scope_id)

        if len(matched) == 0 and scope_id != 'global':
            # if that scope is not defined we can take global data set.
            return self.get_parameter(parameter_name=parameter_name,
                                      pulse_name=pulse_name,
                                      channel=channel,
                                      scope_id='global',
                                      calibration_group=calibration_group)

        # filter out invalid entries
        valid_data = matched.query('validation != "{}"'.format(types.Validation.FAIL.value))

        if len(valid_data) == 0:
            return None

        # pick up the latest entry
        df_idx = valid_data['timestamp'].idxmax()
        pval = matched.loc[df_idx].value

        if parameter_name == 'duration':
            return int(pval)
        else:
            return pval

    def set_parameter(
            self,
            parameter_name: str,
            pulse_name: str,
            channel: str,
            value: Union[int, float, str],
            scope_id: Optional[str] = 'global',
            validation: Optional[str] = None,
            timestamp: Optional[pd.Timestamp] = None,
            exp_id: Optional[str] = None,
            calibration_group: Optional[str] = 'default'
    ):
        """Set waveform parameter to the local database. This is usually used to
        add the result of calibration experiment.

        Args:
            parameter_name: Parameter name to get.
            pulse_name: Name of pulse that the parameter is associated with.
            channel: Name of channel where the pulse is played.
            scope_id: Target scope id string that the pulse belongs to.
            value: Calibrated parameter value.
            validation: Validation status. Defaults to `None`.
            timestamp: Timestamp of when the value is generated. Defaults to current time.
            exp_id: String representing the id of experiment that calibrated this parameter.
            calibration_group: Calibration data set name if multiple sets exist.
        """
        # use special function if parameter is pulse shape
        if parameter_name == 'shape':
            self.set_pulse_shape(
                pulse_name=pulse_name,
                channel=channel,
                pulse_shape=value,
                scope_id=scope_id,
                calibration_group=calibration_group
            )

        # add new data
        self._parameter_collection = self._parameter_collection.append(
            {'qubits': self._channel_qubit_map[channel],
             'channel': channel,
             'pulse_name': pulse_name,
             'calibration_group': calibration_group,
             'scope_id': scope_id,
             'name': parameter_name,
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

    def get_pulse_shape(
            self,
            pulse_name: str,
            channel: str,
            scope_id: Optional[str] = None,
            calibration_group: Optional[str] = 'default'
    ) -> str:
        """A special method to get pulse shape in the database.

        Args:
            pulse_name: Name of target pulse.
            channel: Channel name where pulse is played.
            scope_id: The scope id of pulse where pulse belongs to.
            calibration_group: The name of calibration.

        Returns:
            Name of pulse shape.
        """
        return self.get_parameter(
            parameter_name='shape',
            pulse_name=pulse_name,
            channel=channel,
            scope_id=scope_id,
            calibration_group=calibration_group)

    def set_pulse_shape(
            self,
            pulse_name: str,
            channel: str,
            pulse_shape: str,
            scope_id: Optional[str] = None,
            calibration_group: Optional[str] = 'default'
    ):
        """A special method to save pulse shape in the database.

        Pulse shape is also handled as a parameter in the calibration module.
        To ensure calibration data consistency with pulse shape,
        the `shape` parameter can be defined once for each calibration group.
        To define new pulse shape for the same scope user need to create
        another calibration group.

        Args:
            pulse_name: Name of target pulse.
            channel: Channel name where pulse is played.
            pulse_shape: Name of pulse shape.
            scope_id: The scope id of pulse where pulse belongs to.
            calibration_group: The name of calibration.
        """
        scope_id = scope_id or 'global'

        # duplication check
        existing_entry = self._find_data(
            channel=channel,
            pulse_name=pulse_name,
            calibration_group=calibration_group,
            scope_id=scope_id,
            name='shape'
        )

        if len(existing_entry) > 0:
            raise Exception('Pulse shape for {0} of calibration group {1} '
                            'is already defined. Create another group to define '
                            'new pulse shape.'.format(scope_id, calibration_group))

        # add new data
        self._parameter_collection = self._parameter_collection.append(
            {'qubits': self._channel_qubit_map[channel],
             'channel': channel,
             'pulse_name': pulse_name,
             'calibration_group': calibration_group,
             'scope_id': scope_id,
             'name': 'shape',
             'value': pulse_shape,
             'validation': types.Validation.NONE.value,
             'timestamp': pd.Timestamp.now(),
             'exp_id': None
             },
            ignore_index=True
        )

    def _find_data(
            self,
            qubits: Optional[Union[int, List[int]]] = None,
            channel: Optional[str] = None,
            pulse_name: Optional[str] = None,
            calibration_group: Optional[str] = None,
            scope_id: Optional[str] = None,
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

        # filter by calibration_group
        if calibration_group:
            query_list.append('calibration_group == "{}"'.format(calibration_group))

        # filter by scope_id
        if scope_id:
            query_list.append('scope_id == "{}"'.format(scope_id))

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
