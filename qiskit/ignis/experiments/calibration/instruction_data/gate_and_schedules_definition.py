from typing import Dict, Union, List, Tuple, Iterable

from qiskit import QuantumCircuit, pulse, schedule
from qiskit.circuit import ParameterExpression, Gate, Parameter
from qiskit.pulse import Play, Schedule, ControlChannel, ParametricPulse
from qiskit.pulse.channels import PulseChannel
from qiskit.providers.basebackend import BaseBackend

from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable


class InstructionsDefinition:
    """
    Class to track calibrated instructions for the calibration module of Ignis.

    The class allows users to define single-pulse schedules as quantum circuits and
    then leverage the quantum circuit compose operation to compose more complex
    circuits from basic circuits.
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
    def instructions(self) -> Dict[Tuple[str, Iterable], Union[Schedule, QuantumCircuit]]:
        """Return the instructions as a dict."""
        return self._instructions

    def get_calibration(self):
        """Returns the calibrations."""
        return self._pulse_table.filter_data()

    def get_instruction_template(self, name: str, qubits: Iterable) -> QuantumCircuit:
        """
        Args:
            name: Name of the instruction to get.
            qubits: Set of qubits to which the instruction applies.

        Returns:
            A QuantumCircuit with parameters in it.
        """
        return self._instructions.get((name, qubits), None)

    def get_instruction(self, name: str, qubits: Iterable,
                        free_parameters: List[str] = None) -> QuantumCircuit:
        """
        Returns the QuantumCircuit of the instruction where all parameters aside for those
        explicitly specified are bound to their calibration.

        Args:
            name: name of the instruction to retrive
            qubits: qubits to which the instruction applies.
            free_parameters: Names of the parameter that should be left unbound.
                If None is specified then all parameters will be bound to their
                calibrated values.
        """
        qc = self.get_instruction_template(name, qubits)

        if not free_parameters:
            free_parameters = []

        binding_dict = {}
        for param in qc.parameters:
            if param.name not in free_parameters:
                binding_dict[param] = self._get_parameter_value(param)

        return qc.assign_parameters(binding_dict)

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

        gate = Gate(name=name, num_qubits=len(qubits), params=[_ for _ in params.values()])
        circ = QuantumCircuit(self._n_qubits)  # Probably a better way of doing this
        circ.append(gate, qubits)
        circ.add_calibration(gate, qubits, schedule)

        self._instructions[(name, qubits)] = circ

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

    def add_composite_instruction(self, inst_name: str, instructions: List[List[Tuple[str, set]]]):
        """
        Creates a new instruction from the given list of instructions.

        Args:
            inst_name: Name of the composite instruction to add
            instructions: The instructions to add to the circuit. Instructions are grouped
                by barriers to enforce relative timing between the instructions. Each instruction
                is specified by its name and the qubit it applies to.
        """
        all_qubits = set()
        for inst_list in instructions:
            for inst_config in inst_list:
                all_qubits |= set(inst_config[1])

        circ = QuantumCircuit(self._n_qubits)
        for inst_list in instructions:
            for inst_config in inst_list:
                name = inst_config[0]
                qubits = inst_config[1]
                qc = self.get_instruction_template(name, qubits)
                circ.compose(qc, inplace=True)

            circ.barrier()

        self._instructions[(inst_name, tuple(all_qubits))] = circ
