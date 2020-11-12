from typing import Dict, Callable, List, Tuple, Iterable

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterExpression, Gate, Parameter
from qiskit.pulse import Play, Schedule, ControlChannel, ParametricPulse
from qiskit.pulse.channels import PulseChannel


class InstructionsDefinition:
    """
    Class to track calibrated instructions for the calibration module of Ignis.

    The class allows users to define single-pulse schedules as quantum circuits and
    then leverage the quantum circuit compose operation to compose more complex
    circuits from basic circuits.
    """

    def __init__(self):

        # Dict to store the instructions we are calibrating
        self._instructions = {}

    @property
    def instructions(self) -> Dict[Tuple[str, Iterable], QuantumCircuit]:
        """Return the instructions as a dict."""
        return self._instructions

    def get_instruction_template(self, name: str, qubits: Iterable) -> QuantumCircuit:
        """
        Args:
            name: Name of the instruction to get.
            qubits: Set of qubits to which the instruction applies.

        Returns:
            A QuantumCircuit with parameters in it.
        """
        return self._instructions[(name, qubits)]

    def get_instruction(self, name: str, qubits: Iterable,
                        free_parameters: List = None) -> QuantumCircuit:
        """
        Returns the QuantumCircuit of the instruction where all parameters aside for those
        explicitly specified are bound to their calibration.

        Args:
            name: name of the instruction to retrive
            qubits: qubits to which the instruction applies.
            free_parameters: Parameters that should be left unbound. If None is specified then
                all parameters will be bound to their calibrated values.
        """
        # TODO Get the parameters

        # TODO Get their values

        # TODO return circ with parameters assigned
        raise NotImplemented

    def create_basic_instruction(self, name: str, duration: int, pulse_envelope: ParametricPulse,
                                 channel: PulseChannel, params = None):
        """
        Creates a basic instruction in the dictionary.

        Args:
            name:
            duration: The duration of the pulse schedule.
            pulse_envelope: The callable pulse envelope. Its parameters are given by
                **params after duration is added to it.
            channel: The channel to which we apply the basic instruction.
        """
        # Avoids having the user manage the parameters.
        if not params:
            params = self._basic_inst_parameters(name, channel, pulse_envelope)

        gate = Gate(name=name, num_qubits=1, params=[_ for _ in params.values()])

        if duration:
            params['duration'] = duration

        schedule = Schedule(name=name)
        schedule = schedule.insert(0, Play(pulse_envelope(**params), channel))

        if isinstance(channel, ControlChannel):
            # TODO Need a mapping from ControlChannel to qubits
            # TODO This works for CR, would it work for TC?
            raise NotImplemented
        else:
            qubit = int(channel.name.replace('d', '').replace('m', ''))

        circ = QuantumCircuit(1)
        circ.append(gate, [0])
        circ.add_calibration(gate, [qubit], schedule)

        self._instructions[(name, (qubit, ))] = circ

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

    def add_composite_instruction(self, name: str, instructions: List[List[Tuple[str, set]]]):
        """
        Creates a new instruction from the given list of instructions.

        Args:
            name: Name of the composite instruction to add
            instructions: The instructions to add to the circuit. Instructions are grouped
                by barriers to enforce relative timing between the instructions. Each instruction
                is specified by its name and the qubit it applies to.
        """
        all_qubits = set()
        for inst_list in instructions:
            for inst_config in inst_list:
                all_qubits |= set(inst_config[1])

        circ = QuantumCircuit(max(all_qubits))
        for inst_list in instructions:
            for inst_config in inst_list:
                name = inst_config[0]
                qubits = inst_config[1]
                qc = self.get_instruction_template(name, qubits)
                circ.compose(qc, qubits=qubits)

            circ.barrier()

        self._instructions[(name, all_qubits)] = circ
