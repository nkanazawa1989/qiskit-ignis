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

"""User interface of database."""

import hashlib
from enum import Enum
from typing import Dict, Union, List, Tuple, Optional

import pandas as pd
from qiskit.circuit import Gate
from qiskit.providers.basebackend import BaseBackend
from qiskit.pulse import Schedule

from qiskit import QuantumCircuit
from qiskit.ignis.experiments.calibration.instruction_data import compiler
from qiskit.ignis.experiments.calibration.instruction_data import utils
from qiskit.ignis.experiments.calibration.instruction_data.parameter_table import PulseParameterTable


class InstructionsDefinition:
    """
    Class to track calibrated instructions for the calibration module of Ignis.

    The class allows users to define single-pulse schedules as quantum circuits and
    then leverage the quantum circuit compose operation to compose more complex
    circuits from basic circuits.
    """
    TABLE_COLS = ['gate_name', 'qubits', 'signature', 'gate_id', 'program']

    def __init__(self,
                 backend_name: str,
                 n_qubits: int,
                 channel_qubit_map: Dict[str, Tuple[int]],
                 pulse_table: Optional[PulseParameterTable] = None,
                 parametric_shapes: Optional[Enum] = None,
                 pulse_channels: Optional[Enum] = None):
        """
        Args:
            backend: The backend for which the instructions are defined.
        """

        # Dict to store the instructions we are calibrating
        self._instructions = pd.DataFrame(index=[], columns=InstructionsDefinition.TABLE_COLS)

        # Table to store the calibrated pulse parameters
        self.backend_name = backend_name

        if pulse_table:
            self._pulse_table = pulse_table
        else:
            self._pulse_table = PulseParameterTable(channel_qubit_map=channel_qubit_map)

        self._n_qubits = n_qubits

        self._parametric_shapes = parametric_shapes or utils.ParametricPulseShapes
        self._pulse_channels = pulse_channels or utils.ChannelPrefixes

        # parameter set used to construct schedule
        self._series = 'default'

    @classmethod
    def from_backend(cls, backend: BaseBackend) -> 'InstructionsDefinition':
        """A factory method that creates InstructionSet from BaseBackend.

        Args:
            backend: base backend or other pulse backends that conform to OpenPulse spec.

        Returns:
            New InstructionSet instance.
        """
        # TODO implement this
        # we need a logic to convert Schedule into database code.
        # Schedule doesn't have context. Thus we need to infer the context.

        raise NotImplementedError

        # parameter_library = dict()
        # channel_qubit_map = dict()
        #
        # for chname, ch_properties in backend.configuration().channels.items():
        #     channel_qubit_map[chname] = tuple(ch_properties['operates']['qubits'])
        #
        # pulse_table, sched_template = parse_backend_instmap(
        #     channel_qubit_map=channel_qubit_map,
        #     instmap=backend.defaults(refresh=True).instruction_schedule_map,
        #     parameter_library=parameter_library)
        #
        # return InstructionsDefinition(
        #     backend_name=backend.name(),
        #     n_qubits=backend.configuration().n_qubits,
        #     channel_qubit_map=channel_qubit_map,
        #     pulse_table=pulse_table)

    @property
    def parametric_shapes(self) -> Enum:
        """Return the definition of parametric pulses."""
        return self._parametric_shapes

    @property
    def pulse_channels(self) -> Enum:
        """Return the definition of pulse channels."""
        return self._pulse_channels

    @property
    def series(self) -> str:
        """Return the current data series to construct gate schedule."""
        return self._series

    @series.setter
    def series(self, new_series):
        """Set new series name."""
        self._series = new_series

    @property
    def instructions(self) -> pd.DataFrame:
        """Return the instructions as a data frame."""
        return self._instructions

    @property
    def pulse_parameter_table(self) -> PulseParameterTable:
        """Returns the table of pulse parameters."""
        return self._pulse_table

    def get_calibration(self):
        """Returns the calibrations."""
        return self._pulse_table.filter_data()

    def get_circuit(self,
                    gate_name: str,
                    qubits: Tuple,
                    free_parameter_names: List[str] = None) -> QuantumCircuit:
        """
        Wraps the schedule from the instructions table in a quantum circuit.

        Args:
            gate_name: name of the instruction to retrive
            qubits: qubits to which the instruction applies.
            free_parameter_names: Names of the parameter that should be left unbound.
                If None is specified then all parameters will be bound to their
                calibrated values.
        """
        schedule = self.get_gate_schedule(gate_name, qubits, free_parameter_names)

        gate = Gate(name=gate_name, num_qubits=len(qubits), params=list(schedule.parameters))
        circ = QuantumCircuit(self._n_qubits)  # Probably a better way of doing this
        circ.append(gate, qubits)
        circ.add_calibration(gate, qubits, schedule, params=schedule.parameters)

        return circ

    def add_gate_schedule(self,
                          gate_name: str,
                          qubits: Union[int, Tuple[int]],
                          signature: List[str],
                          schedule: Schedule):
        """"""
        # TODO implement this
        raise NotImplementedError

    def get_gate_schedule(self,
                          gate_name: Optional[str] = None,
                          qubits: Optional[Union[int, Tuple[int]]] = None,
                          gate_id: Optional[str] = None,
                          free_parameter_names: Optional[List[str]] = None) -> Schedule:
        """
        Retrieves a schedule from the instructions data frame.

        User can specify (gate_name, qubits) or unique schedule id to retrieve target schedule.

        Args:
            gate_name: Name of the schedule to retrive.
            qubits: qubits for which to get the schedule.
            gate_id: Unique id of target schedule.
            free_parameter_names: List of parameter names that will be left unassigned.
                The parameter assignment is done by querying the pulse parameter table.

        Returns:
            schedule for the given input.
        """
        matched_entries = self._find_entries(gate_name, qubits, gate_id)

        if len(matched_entries) > 1:
            raise Exception('Multiple entries are found. Database may be broken.')

        program_parser = compiler.NodeVisitor(self)

        return program_parser(
            source=matched_entries.iloc[0].program,
            gate_id=matched_entries.iloc[0].gate_id,
            free_parameters=free_parameter_names
        )

    def _add_gate_schedule(self,
                           gate_name: str,
                           qubits: Union[int, Tuple[int]],
                           signature: List[str],
                           sched_code: str) -> str:
        """A helper function to add new gate schedule to the database.

        Args:
            gate_name: Gate name of this entry.
            qubits: Qubit associated with this gate.
            signature: A list of parameters passed to the instruction map.
            sched_code: A string code representing pulse schedule.

        Returns:
            Generated gate id for this entry.
        """
        if isinstance(qubits, int):
            qubits = (qubits, )

        gate_id = self._deduplicate_gate_id(gate_name, qubits)

        self._instructions = self._instructions.append(
            {'gate_name': gate_name,
             'qubits': qubits,
             'signature': signature,
             'gate_id': gate_id,
             'program': sched_code},
            ignore_index=True
        )

        return gate_id

    def _deduplicate_gate_id(self, gate_name: str, qubits: Tuple[int]) -> str:
        """A helper function to create unique gate id."""
        ident = 0
        while True:
            base_str = '{0}.{1}:{2}'.format(gate_name, '_'.join(map(str, qubits)), ident)
            temp_id = hashlib.md5(base_str.encode('utf-8')).hexdigest()[:6]
            existing_ents = self._find_entries(gate_id=temp_id)
            # we don't assume there are multiple schedules for single gate
            if len(existing_ents) == 0:
                return temp_id
            ident += 1

    def _find_entries(self,
                      gate_name: Optional[str] = None,
                      qubits: Optional[Union[int, Tuple[int]]] = None,
                      gate_id: Optional[str] = None) -> pd.DataFrame:
        """A helper method to find schedule entry."""
        query_list = []

        # filter by gate name
        if gate_name:
            query_list.append('gate_name == "{}"'.format(gate_name))

        # filter by qubits
        if qubits is not None:
            if isinstance(qubits, int):
                qubits = (qubits, )
            query_list.append('qubits == tuple({})'.format(str(qubits)))

        # filter by schedule unique id
        if gate_id:
            query_list.append('gate_id == "{}"'.format(gate_id))

        query_str = ' and '.join(query_list)

        if query_str:
            return self._instructions.query(query_str)
        else:
            return self._instructions
