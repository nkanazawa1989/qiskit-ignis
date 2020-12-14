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

"""Compile calibration schedule DSL to pulse Schedule."""

import dataclasses
import re
from abc import ABCMeta
from enum import Enum
from typing import List, Dict, NamedTuple, Iterator, Union, Optional, Tuple

from qiskit import pulse, circuit
from qiskit.ignis.experiments.calibration.instruction_data import utils


#
# Definitions
#

class OpenPulseChannels(Enum):
    """Map the channel name prefix to Qiskit Channel object.

    The enum name is the channel prefix, the value is its mapping to the class.
    """
    d = pulse.DriveChannel
    u = pulse.ControlChannel
    m = pulse.MeasureChannel
    a = pulse.AcquireChannel


class ParametricPulseShapes(Enum):
    """Map the pulse shape name to the pulse module waveforms.

    The enum name is the DSL name for pulse shapes, the
    value is its mapping to the OpenPulse Command in Qiskit.
    """
    gaus = pulse.Gaussian
    gaus_sq = pulse.GaussianSquare
    drag = pulse.Drag
    constant = pulse.Constant


class TokenSpec(Enum):
    """Map the Abstract Syntax Tree (AST) node name to the calibration schedule Domain Specific Language (DSL) syntax.

    The enum name is the AST node type, the value is its mapping to the DSL syntax.
    """
    CONTEXT_ENTER = r'\[(?P<pos>right|left|seq)\]{'
    CONTEXT_EXIT = r'}'
    REFERENCE = r'%(?P<name>[\w]*)\((?P<qubits>[0-9,]+)\)'
    PULSE = r'%(?P<name>[\w]*).(?P<channel>[a-z][0-9]+)'
    FRAME = r'$(?P<name>[\w]*)\((?P<channel>[a-z][0-9]+),(?P<operand>[0-9.]+)\)'


#
# Create token from input string
#

Token = NamedTuple('Token', [('type', str), ('data', Dict[str, str])])


def _tokenizer(source: str) -> Iterator[Token]:
    """A helper function to generate token from code string.

    Args:
        source: Input calibration schedule DSL.

    Returns:
        Iterator of token object.
    """
    source = source.replace(' ', '')
    while source:
        for spec in TokenSpec:
            matched_obj = re.match(spec.value, source)
            if matched_obj:
                source = source[matched_obj.end():]
                token = Token(spec.name, matched_obj.groupdict())
                break
        else:
            raise Exception('Invalid syntax {source}'.format(source=source))
        yield token


#
# Create AST from token list
#

@dataclasses.dataclass(frozen=True)
class Inst(metaclass=ABCMeta):
    """A base class of instruction. This class is meant to be subclassed."""
    name: str


@dataclasses.dataclass(frozen=True)
class PulseInst(Inst):
    """A leaf that represents a play schedule component."""
    channel: str

    def __repr__(self):
        return 'Pulse({}.{})'.format(self.name, self.channel)


@dataclasses.dataclass(frozen=True)
class FrameInst(Inst):
    """A leaf that represents non-pulse schedule component such as frame change."""
    channel: str
    operand: float

    def __repr__(self):
        return 'Frame({},{})'.format(self.name, self.operand)


@dataclasses.dataclass(frozen=True)
class Reference(Inst):
    """A leaf that represents a reference to another schedule definition."""
    qubits: Tuple[int]

    def __repr__(self):
        return 'Ref({}:{})'.format(self.name, ','.join(map(str, self.qubits)))


@dataclasses.dataclass
class ScheduleBlock:
    """A node that represents a block of schedule components, left-aligned by default."""
    context_type: str = 'left'
    children: List[Union[Inst, 'ScheduleBlock']] = dataclasses.field(default_factory=list)


def parse(source: str) -> ScheduleBlock:
    """A parser to generate abstract syntax tree from source code.

    Args:
        source: Input calibration schedule DSL.

    Returns:
        Abstract syntax tree of input pulse schedule program.
    """
    schedule = ScheduleBlock()
    stack = []
    for token in _tokenizer(source):
        if token.type in [TokenSpec.PULSE.name, TokenSpec.REFERENCE.name, TokenSpec.FRAME.name]:
            # add instruction to parent schedule block
            if stack:
                stack[-1].children.append(_parse_node(token))
            else:
                schedule.children.append(_parse_node(token))
        elif token.type == TokenSpec.CONTEXT_ENTER.name:
            # create child schedule block and add this to stack
            stack.append(ScheduleBlock(context_type=token.data['pos']))
        elif token.type == TokenSpec.CONTEXT_EXIT.name:
            # close child schedule block and append this to parent block
            if not stack:
                raise Exception('No context enter found.')
            current_context = stack.pop(-1)
            if stack:
                stack[-1].children.append(current_context)
            else:
                schedule.children.append(current_context)
        else:
            raise Exception('Invalid token {token} is specified.'.format(token=token.type))

    return schedule


def _parse_node(token: Token) -> Inst:
    """A helper function to create AST node from token.

    Args:
        token: Input token.

    Returns:
        Node corresponding to the input token.
    """
    # pulse
    if token.type == TokenSpec.PULSE.name:
        return PulseInst(**token.data)
    # pulse
    if token.type == TokenSpec.FRAME.name:
        return FrameInst(**token.data)
    # reference
    if token.type == TokenSpec.REFERENCE.name:
        qubits = tuple(map(int, token.data['qubits'].split(',')))
        return Reference(name=token.data['name'], qubits=qubits)

    raise Exception('Invalid token {token} is specified as instruction.'.format(token=token.type))


#
# Create pulse program from AST
#

class NodeVisitor:
    """Create pulse schedule from abstract syntax tree."""
    chan_regex = re.compile(r'([a-zA-Z]+)(\d+)')

    def __init__(self, inst_def: 'InstructionsDefinition'):
        """Create new parser.

        Args:
              inst_def: Instruction definition object.
        """
        self._inst_def = inst_def

        # these parameters are set on the fly
        # TODO remove them
        self._scope_id = None
        self._calibration_group = None
        self._free_parameters = []
        self._defined_parameter = dict()

    def __call__(self,
                 source: str,
                 scope_id: str,
                 calibration_group: str,
                 free_parameters: Optional[List[str]] = None) -> pulse.Schedule:
        """Parse source code and return Schedule.

        TODO remove gate_id and free parameters from parser.
        Blocker is parametrization of pulse duration.
        If we can parametrize the duration, we can populate schedule with unbound parameters and
        parser doesn't need to call parameter table to get integer duration.
        Thus everything can be correctly offloaded the parameter binding operation
        to the get_gate_schedule method that calls this parser.

        Args:
            source: Calibration DSL representing a pulse schedule.

        Returns:
            Pulse schedule object.
        """
        self._scope_id = scope_id
        self._calibration_group = calibration_group
        self._free_parameters = free_parameters or []
        self._defined_parameter.clear()

        return self.visit(parse(source))

    def _get_channel(self, ch_str: str) -> pulse.channels.Channel:
        """A helper function to convert channel string into Qiskit object.

        Args:
            ch_str: String representation of channel.

        Returns:
            Qiskit pulse channel object.
        """
        match = self.chan_regex.match(ch_str)
        if match:
            prefix, index = match.group(1), int(match.group(2))
            channel = OpenPulseChannels[prefix].value

            return channel(index=index)

        raise Exception('Channel name {name} is not correct syntax.'.format(name=ch_str))

    def _get_parameter(self, composite_name: str) -> circuit.Parameter:
        """A helper function to create parameter. Reuse defined parameter names.

        Args:
            composite_name: Parameter name.

        Returns:
            Qiskit parameter object.
        """
        if composite_name in self._defined_parameter:
            param_obj = self._defined_parameter[composite_name]
        else:
            param_obj = circuit.Parameter(composite_name)
            self._defined_parameter[composite_name] = param_obj

        return param_obj

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method)

        return visitor(node)

    def visit_PulseInst(self, node: PulseInst) -> pulse.Instruction:
        """Evaluate pulse instruction node and return play instruction.

        Args:
            node: PulseInst node to evaluate.

        Returns:
            Play instruction.
        """
        # get pulse shape
        shape = self._inst_def.pulse_parameter_table.get_pulse_shape(
            pulse_name=node.name,
            channel=node.channel,
            scope_id=self._scope_id,
            calibration_group=self._calibration_group
        )
        parametric_pulse = self._inst_def.parametric_shapes[shape].value

        # generate parameter names on the fly
        parametric_pulse_kwargs = dict()
        for pname in utils.get_pulse_parameters(parametric_pulse):
            composite_name = self._inst_def.pulse_parameter_table.get_full_name(
                parameter_name=pname,
                pulse_name=node.name,
                channel=node.channel,
                scope_id=self._scope_id,
                calibration_group=self._calibration_group
            )
            # TODO calling parameter biding here is bit strange.
            # This parameter binding should be offloaded to the get_gate_schedule method.
            # However, we cannot do this now because of parametrization of duration.
            # The role of parser is to create program, not the parameter-bound schedule.
            param_val = self._inst_def.pulse_parameter_table.get_parameter(
                parameter_name=pname,
                pulse_name=node.name,
                channel=node.channel,
                scope_id=self._scope_id,
                calibration_group=self._calibration_group
            )
            if param_val is not None and composite_name not in self._free_parameters:
                parametric_pulse_kwargs[pname] = param_val
            else:
                parametric_pulse_kwargs[pname] = self._get_parameter(composite_name)

        # pulse name for visualization purpose
        pulse_name = '{}.{}.{}'.format(node.name, node.channel, self._scope_id)
        played_pulse = parametric_pulse(**parametric_pulse_kwargs, name=pulse_name)
        channel = self._get_channel(node.channel)

        return pulse.Play(played_pulse, channel)

    def visit_FrameInst(self, node: FrameInst) -> pulse.Instruction:
        """Evaluate frame instruction node and return frame change instruction.

        Args:
            node: FrameInst node to evaluate.

        Returns:
            Arbitrary frame change instruction specified by AST name.
        """
        raise NotImplementedError

    def visit_Reference(self, node: Reference) -> pulse.Schedule:
        """Evaluate reference node and return arbitrary schedule.

        Args:
            node: Reference node to evaluate.

        Returns:
            Arbitrary schedule from another schedule database entry.
        """
        return self._inst_def.get_schedule(
            gate_name=node.name,
            qubits=node.qubits,
            free_parameter_names=self._free_parameters
        )

    def visit_ScheduleBlock(self, node: ScheduleBlock) -> pulse.Schedule:
        """Return the pulse Schedule defined by the input ScheduleBlock.

        Args:
            node: Schedule block node to evaluate.

        Returns:
            Arbitrary schedule defined by its children nodes.
        """
        sched_block = pulse.Schedule()
        for sched_component in list(map(self.visit, node.children)):
            sched_block.append(sched_component, inplace=True)

        if node.context_type == 'left':
            return pulse.transforms.align_left(sched_block)
        elif node.context_type == 'right':
            return pulse.transforms.align_right(sched_block)
        elif node.context_type == 'seq':
            return pulse.transforms.align_sequential(sched_block)

        raise Exception('Invalid alignment {type} is specified.'.format(type=node.context_type))
