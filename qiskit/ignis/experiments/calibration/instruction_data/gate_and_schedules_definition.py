from typing import Dict, Union, List, Tuple, Iterable

from qiskit import QuantumCircuit, pulse, schedule
from qiskit.circuit import ParameterExpression, Gate, Parameter
from qiskit.pulse import (Play, Schedule, ControlChannel, ParametricPulse, DriveChannel,
                          MeasureChannel)
from qiskit.pulse.channels import PulseChannel
from qiskit.providers.basebackend import BaseBackend

from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable

class InstructionsDefinition:
    """
    Class to track calibrated instructions for the calibration module of Ignis.

    The class allows users to define single-pulse schedules as quantum circuits and
    then leverage the quantum circuit compose operation to compose more complex
    circuits from basic circuits.

    TODO
    - parameter binding is global, these needs to be made local
    - test recursive behavior of instructions
    """

    def __init__(self, backend: BaseBackend):
        """
        Args:
            backend: The backend for which the instructions are defined.
        """

        # Dict to store the instructions we are calibrating
        self._instructions = {}

        # Table to store the calibrated pulse parameters
        self._pulse_table = PulseTable()
        self._n_qubits = backend.configuration().n_qubits
        self._channel_map = backend.configuration().qubit_channel_mapping
        self._backend = backend

    @property
    def instructions(self) -> Dict[Tuple[str, Iterable], Schedule]:
        """Return the instructions as a dict."""
        return self._instructions

    def get_calibration(self):
        """Returns the calibrations."""
        return self._pulse_table.filter_data()

    def get_circuit_template(self, name: str, qubits: Tuple) -> QuantumCircuit:
        """
        Args:
            name: Name of the instruction to get.
            qubits: Set of qubits to which the instruction applies.

        Returns:
            A QuantumCircuit with parameters in it.
        """
        schedule = self._instructions.get((name, qubits), Schedule())

        if not isinstance(schedule, Schedule):
            schedule = self.get_composite_instruction(schedule)

        gate = Gate(name=name, num_qubits=len(qubits), params=schedule.parameters)
        circ = QuantumCircuit(self._n_qubits)  # Probably a better way of doing this
        circ.append(gate, qubits)
        circ.add_calibration(gate, qubits, schedule, params=schedule.parameters)

        return circ

    def get_circuit(self, name: str, qubits: Tuple,
                    free_parameter_names: List[str] = None) -> QuantumCircuit:
        """
        Returns the QuantumCircuit of the instruction where all parameters aside for those
        explicitly specified are bound to their calibration.

        Args:
            name: name of the instruction to retrive
            qubits: qubits to which the instruction applies.
            free_parameter_names: Names of the parameter that should be left unbound.
                If None is specified then all parameters will be bound to their
                calibrated values.
        """
        schedule = self._instructions[(name, qubits)]

        if not isinstance(schedule, Schedule):
            schedule = self.get_composite_instruction(schedule)

        if not free_parameter_names:
            free_parameter_names = []

        binding_dict = {}
        for param in schedule.parameters:
            print(param.name)
            if param.name not in free_parameter_names:
                binding_dict[param] = self._get_parameter_value(param)

        schedule = schedule.assign_parameters(binding_dict)

        gate = Gate(name=name, num_qubits=len(qubits), params=schedule.parameters)
        circ = QuantumCircuit(self._n_qubits)  # Probably a better way of doing this
        circ.append(gate, qubits)
        circ.add_calibration(gate, qubits, schedule, params=schedule.parameters)

        return circ

    def _get_parameter_value(self, parameter: ParameterExpression) -> Union[float, int, complex]:
        """
        Helper method.

        TODO This could be simplified by better integrating with PulseTable
        """
        inst_name, channel, name = parameter.name.split('.')
        qubits = self._get_qubits(channel)

        return list(self._pulse_table.get_parameter(qubits, channel, inst_name, '', 1.0, name).values())[0].value

    def _add_parameter(self, parameter: ParameterExpression, value: Union[float, int, complex]):
        """
        Helper method for current implementation.

        TODO This should/could be moved to PulseTable

        Args:
            parameter: A parameter to add to the DB.
            value: The value of the parameter to add to the DB.
        """
        inst_name, channel, name = parameter.name.split('.')
        qubits = self._get_qubits(channel)

        # TODO see if this will stay like this
        pulse_type = ''

        self._pulse_table.set_parameter(qubits, channel, inst_name, pulse_type, 1.0, name, value)

    def _get_qubits(self, channel_name: str) -> Tuple[int]:
        """Helper method to get qubits from channel name."""
        if channel_name[0] in ['d', 'm']:
            return (int(channel_name[1:]), )
        else:
            qubits = []
            for qubit_idx, channels in enumerate(self._channel_map):
                if channel_name in channels:
                    qubits.append(qubit_idx)

            return tuple(qubits)

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
        qubits = self._get_qubits(channel.name)

        self._instructions[(name, qubits)] = schedule

    def _basic_inst_parameters(self, name: str, channel: PulseChannel,
                               pulse_envelope: ParametricPulse) -> Dict[str, ParameterExpression]:
        """
        This functions avoids the user to have to manage parameters and their name.

        TODO Is there a better way of doing this?
        """
        params = {}
        if pulse_envelope.__name__ in ['Drag', 'Gaussian', 'GaussianSquare']:
            params['amp'] = Parameter(name + '.' + channel.name + '.amp')
            params['sigma'] = Parameter(name + '.' + channel.name + '.sigma')

        if pulse_envelope.__name__ == 'Drag':
            params['beta'] = Parameter(name + '.' + channel.name + '.beta')

        if pulse_envelope.__name__ == 'GaussianSquare':
            params['width'] = Parameter(name + '.' + channel.name + '.width')

        return params

    def add_composite_instruction(self, inst_name: str, instructions: List[List[Tuple[str, Tuple]]]):
        """
        A composite instruction is an instruction that refers to other instructions.
        It is specified as a list of list where timing barriers are inserted in between
        lists. All instructions within a sublist are left aligned.
        """

        qubits = set()
        for inst_list in instructions:
            for inst_config in inst_list:
                qubits |= set(inst_config[1])

        self._instructions[(inst_name, tuple(qubits))] = instructions

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
