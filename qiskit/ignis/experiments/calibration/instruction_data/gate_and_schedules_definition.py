import copy
from typing import Dict, Union, List, Tuple, Iterable, Optional

from qiskit import QuantumCircuit, pulse, schedule
from qiskit.circuit import ParameterExpression, Gate, Parameter
from qiskit.pulse import (Play, Schedule, ControlChannel, ParametricPulse, DriveChannel,
                          MeasureChannel)
from qiskit.pulse.channels import PulseChannel
from qiskit.providers.basebackend import BaseBackend
from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable
from qiskit.ignis.experiments.calibration.instruction_data.utils import parse_backend_instmap


class InstructionsDefinition:
    """
    Class to track calibrated instructions for the calibration module of Ignis.

    The class allows users to define single-pulse schedules as quantum circuits and
    then leverage the quantum circuit compose operation to compose more complex
    circuits from basic circuits.

    # TODO
    - test recursive behavior of instructions
    """

    def __init__(self, backend_name: str, n_qubits: int, channel_qubit_map: Dict,
                 pulse_table: Optional[PulseTable] = None):
        """
        Args:
            backend: The backend for which the instructions are defined.
        """

        # Dict to store the instructions we are calibrating
        self._instructions = {}

        # Table to store the calibrated pulse parameters
        self.backend_name = backend_name

        if pulse_table:
            self._pulse_table = pulse_table
        else:
            self._pulse_table = PulseTable()

        self._n_qubits = n_qubits
        self._channel_map = channel_qubit_map

    @classmethod
    def from_backend(cls, backend: BaseBackend) -> 'InstructionsDefinition':
        """A factory method that creates InstructionSet from BaseBackend.

        Args:
            backend: base backend or other pulse backends that conform to OpenPulse spec.

        Returns:
            New InstructionSet instance.
        """
        parameter_library = dict()
        channel_qubit_map = dict()

        for chname, ch_properties in backend.configuration().channels.items():
            channel_qubit_map[chname] = tuple(ch_properties['operates']['qubits'])

        pulse_table, sched_template = parse_backend_instmap(
            channel_qubit_map=channel_qubit_map,
            instmap=backend.defaults(refresh=True).instruction_schedule_map,
            parameter_library=parameter_library)

        return InstructionsDefinition(
            backend_name=backend.name(),
            n_qubits=backend.configuration().n_qubits,
            channel_qubit_map=channel_qubit_map,
            pulse_table=pulse_table)

    @property
    def instructions(self) -> Dict[Tuple[str, Iterable], Schedule]:
        """Return the instructions as a dict."""
        return self._instructions

    def get_calibration(self):
        """Returns the calibrations."""
        return self._pulse_table.filter_data()

    def get_circuit(self, name: str, qubits: Tuple,
                    free_parameter_names: List[str] = None) -> QuantumCircuit:
        """
        Wraps the schedule from the instructions table in a quantum circuit.

        Args:
            name: name of the instruction to retrive
            qubits: qubits to which the instruction applies.
            free_parameter_names: Names of the parameter that should be left unbound.
                If None is specified then all parameters will be bound to their
                calibrated values.
        """
        schedule = self.get_schedule(name, qubits, free_parameter_names)

        gate = Gate(name=name, num_qubits=len(qubits), params=schedule.parameters)
        circ = QuantumCircuit(self._n_qubits)  # Probably a better way of doing this
        circ.append(gate, qubits)
        circ.add_calibration(gate, qubits, schedule, params=schedule.parameters)

        return circ

    def get_schedule(self, name: str, qubits: Tuple,
                     free_parameter_names: Optional[List[str]] = None) -> Schedule:
        """
        Retrieves a schedule from the instructions dictionary.

        Args:
            name: Name of the schedule to retrive.
            qubits: qubits for which to get the schedule.
            free_parameter_names: List of parameter names that will be left unassigned.
                The parameter assignment is done by querying the pulse parameter table.

        Returns:
            schedule for the given (name, qubits) key.
        """
        schedule = self._instructions[(name, qubits)]

        if not isinstance(schedule, Schedule):
            schedule = self.get_composite_instruction(schedule)

        schedule = copy.deepcopy(schedule)

        if not free_parameter_names:
            free_parameter_names = []

        binding_dict = {}
        for param in schedule.parameters:
            if param.name not in free_parameter_names:
                binding_dict[param] = self._get_parameter_value(param)

        schedule.assign_parameters(binding_dict)

        return schedule

    def _get_parameter_value(self, parameter: ParameterExpression) -> Union[float, int, complex]:
        """
        Helper method.

        TODO This could be simplified by better integrating with PulseTable
        """
        inst_name, ch, pulse_type, name = parameter.name.split('.')
        qubits = self._channel_map[ch]

        return list(self._pulse_table.get_parameter(qubits, ch, inst_name, pulse_type, 1.0, name).values())[0].value

    def _add_parameter(self, parameter: ParameterExpression, value: Union[float, int, complex],
                       stretch_factor: Optional[float] = 1.0):
        """
        Helper method for current implementation.

        TODO This should/could be moved to PulseTable

        Args:
            parameter: A parameter to add to the DB.
            value: The value of the parameter to add to the DB.
            stretch_factor: The stretch factor of the gate.
        """
        inst_name, ch, pulse_type, name = parameter.name.split('.')
        qubits = self._channel_map[ch]

        self._pulse_table.set_parameter(qubits, ch, inst_name, pulse_type, stretch_factor, name, value)

    def create_basic_instruction(self, name: str, duration: int, pulse_envelope: ParametricPulse,
                                 channel: PulseChannel, calibrations: Dict = None):
        """
        Creates a basic instruction in the dictionary.

        Args:
            name:
            duration: The duration of the pulse schedule.
            pulse_envelope: The callable pulse envelope. Its parameters are given by
                **params after duration is added to it.
            channel: The channel to which we apply the basic instruction.
            calibrations: Dictionary with calibrated values for the pulse parameters.
        """
        # Avoids having the user manage the parameters.
        params = self._basic_inst_parameters(name, channel, pulse_envelope)

        if not calibrations:
            calibrations = {}

        # Add the parameters with their calibrated values to the table
        for param_name, param in params.items():
            self._add_parameter(param, calibrations.get(param_name, None))

        if duration:
            params['duration'] = duration

        schedule = Schedule(name=name)
        schedule = schedule.insert(0, Play(pulse_envelope(**params), channel))

        # Identify the qubits concerned by this operation.
        qubits = self._channel_map[channel.name]

        self._instructions[(name, qubits)] = schedule

    @staticmethod
    def _basic_inst_parameters(name: str, channel: PulseChannel,
                               pulse_envelope: ParametricPulse) -> Dict[str, ParameterExpression]:
        """
        This functions avoids the user to have to manage parameters and their name.

        TODO Is there a better way of doing this?
        """
        pulse_name = pulse_envelope.__name__.lower()
        params = {}
        if pulse_envelope.__name__ in ['Drag', 'Gaussian', 'GaussianSquare']:
            params['amp'] = Parameter(name + '.' + channel.name + '.' + pulse_name + '.amp')
            params['sigma'] = Parameter(name + '.' + channel.name + '.' + pulse_name + '.sigma')

        if pulse_envelope.__name__ == 'Drag':
            params['beta'] = Parameter(name + '.' + channel.name + '.' + pulse_name + '.beta')

        if pulse_envelope.__name__ == 'GaussianSquare':
            params['width'] = Parameter(name + '.' + channel.name + '.' + pulse_name + '.width')

        return params

    def add_composite_instruction(self, name: str, instructions: List[List[Tuple[str, Tuple]]]):
        """
        A composite instruction is an instruction that refers to other instructions.
        It is specified as a list of list where timing barriers are inserted in between
        lists. All instructions within a sublist are left aligned.

        Args:
            name: The name of the composite instruction.
            instructions: List of sub-lists which contain references to
                instructions as (name, qubits) keys. Here, name is a string and
                qubits is a tuple. Each instruction is a schedule. All pulses within
                 a sub-list are left-aligned and form a sub-schedule. Sub-schedules are
                 inserted one after the other without any time overlap.
        """

        qubits = set()
        for inst_list in instructions:
            for inst_config in inst_list:
                qubits |= set(inst_config[1])

        self._instructions[(name, tuple(qubits))] = instructions

    def get_composite_instruction(self, instructions: List[List[Tuple[str, Tuple]]]) -> Schedule:
        """
        Recursive function to obtain a schedule.
        """

        schedule = Schedule()
        for inst_list in instructions:
            with pulse.build() as sub_schedule:
                for inst_config in inst_list:
                    name = inst_config[0]
                    qubits = inst_config[1]
                    inst = self._instructions[(name, qubits)]

                    if not isinstance(inst, Schedule):
                        sched = self.get_composite_instruction(inst)
                    else:
                        sched = inst

                    sub_schedule.append(sched, inplace=True)

            schedule.insert(schedule.duration, sub_schedule, inplace=True)

        return schedule
