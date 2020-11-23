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
import inspect
from enum import Enum
from typing import List, Dict, NamedTuple, Iterator, Union, Optional

from qiskit import pulse, circuit
from qiskit.ignis.experiments.calibration.instruction_data import utils


class TokenSpec(Enum):
    """Map the AST node name to the DSL syntax.

    The enum name is the AST node type, the value is its mapping to the DSL syntax.
    """
    CONTEXT_ENTER = r'\[(?P<pos>right|left|seq)\]{'
    CONTEXT_EXIT = r'}'
    REFERENCE = r'&(?P<name>[\w]*)'
    PULSE = r'%(?P<name>[\w]*)\((?P<channel>[a-z][0-9]+),(?P<shape>[\w]*)\)'
    FRAME = r'$(?P<name>[\w]*)\((?P<channel>[a-z][0-9]+),(?P<operand>[0-9.]+)\)'


class ParametricPulseShapes(Enum):
    """Map the pulse shape name to the pulse module waveforms.

    The enum name is the DSL name for pulse shapes, the
    value is its mapping to the OpenPulse Command in Qiskit.
    """
    gaus = pulse.Gaussian
    gaus_sq = pulse.GaussianSquare
    drag = pulse.Drag
    constant = pulse.Constant


class ChannelPrefixes(Enum):
    """Map the pulse channel name to the pulse module channel object.

    The enum name is the channel prefix, the
    value is its mapping to the OpenPulse Channel in Qiskit.
    """
    d = pulse.DriveChannel
    u = pulse.ControlChannel
    m = pulse.MeasureChannel
    a = pulse.AcquireChannel


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
class Inst:
    """A base class of instruction. This class is meant to be subclassed."""
    name: str


@dataclasses.dataclass(frozen=True)
class PulseInst(Inst):
    """A leaf that represents a play schedule component."""
    channel: str
    shape: str

    def __repr__(self):
        return 'Pulse({}.{}.{})'.format(self.name, self.channel, self.shape)


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

    def __repr__(self):
        return 'Ref({})'.format(self.name)


@dataclasses.dataclass
class ScheduleBlock:
    """A node that represents a block of schedule components."""
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
        return Reference(**token.data)

    raise Exception('Invalid token {token} is specified as instruction.'.format(token=token.type))


#
# Create pulse program from AST
#

class NodeVisitor:
    """Create pulse schedule from abstract syntax tree."""
    chan_regex = re.compile(r'([a-zA-Z]+)(\d+)')

    def __init__(self):
        """"""
        self.inst_def = None
        self.id = None
        self.free_parameters = []
        self.shape_map = ParametricPulseShapes
        self.channel_map = ChannelPrefixes

    def __call__(self,
                 source: str,
                 free_parameters: Optional[List[str]]) -> pulse.Schedule:
        """Parse source code and return Schedule.

        Args:
            source: Calibration DSL representing a pulse schedule.

        Returns:
            Pulse schedule object.
        """
        self.free_parameters = free_parameters
        tree = parse(source)

        return self.visit(tree)

    def _get_channel(self, ch_str: str) -> pulse.Channel:
        """A helper function to convert channel string into Qiskit object.

        Args:
            ch_str: String representation of channel.

        Returns:
            Qiskit pulse channel object.
        """
        match = self.chan_regex.match(ch_str)
        if match:
            prefix, index = match.group(1), int(match.group(2))
            return self.channel_map[prefix](index=index)

        raise Exception('Channel name {name} is not correct syntax.'.format(name=ch_str))

    def _get_parameter_names(self, pulse_shape: pulse.ParametricPulse) -> List[str]:
        """A helper function to extract a list of parameter names to construct the class.

        Args:
            pulse_shape: Parametric pulse subclass.

        Returns:
            List of parameter names except for `self` and `name`.
        """
        removes = ['self', 'name']

        const_signature = inspect.signature(pulse_shape.__init__)

        pnames = []
        for pname in const_signature.parameters.keys():
            if pname not in removes:
                pnames.append(pname)

        return pnames

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method)

        return visitor(node)

    def visit_PulseInst(self, node: PulseInst):
        """Evaluate pulse instruction node and return play instruction.

        Args:
            node: PulseInst node to evaluate.

        Returns:
            Play instruction.
        """
        parametric_pulse = self.shape_map[node.shape]

        # get parameters from table
        query = (node.name, node.channel, self.id)
        stored_parameters = self.inst_def.pulse_parameter_table.get_instruction_kwargs(*query)

        # generate parameter names on the fly
        parametric_pulse_kwargs = dict()
        for pname in self._get_parameter_names(parametric_pulse):
            scoped_pname = utils.add_scope(pname, node.channel, node.name)
            if scoped_pname in self.free_parameters or pname not in stored_parameters:
                # parametrize if free parameter or no entry in the database
                parametric_pulse_kwargs[pname] = circuit.Parameter(scoped_pname)
            else:
                parametric_pulse_kwargs[pname] = stored_parameters[pname]

        played_pulse = parametric_pulse(**parametric_pulse_kwargs)
        channel = self._get_channel(node.channel)

        return pulse.Play(played_pulse, channel)

    def visit_FrameInst(self, node: FrameInst):
        """Evaluate frame instruction node and return frame change instruction.

        Args:
            node: FrameInst node to evaluate.

        Returns:
            Arbitrary frame change instruction specified by AST name.
        """
        raise NotImplementedError

    def visit_Reference(self, node: Reference):
        """Evaluate reference node and return arbitrary schedule.

        Args:
            node: Reference node to evaluate.

        Returns:
            Arbitrary schedule from another schedule database entry.
        """
        return self.inst_def.get_schedule(node.name)

    def visit_ScheduleBlock(self, node: ScheduleBlock):
        """Evaluate schedule block node and return arbitrary schedule.

        Args:
            node: Schedule block node to evaluate.

        Returns:
            Arbitrary schedule defined by its children nodes.
        """
        sched_block = pulse.Schedule()
        for sched_component in list(map(self.visit, node.children)):
            sched_block.append(sched_component)

        if node.context_type == 'left':
            return pulse.transforms.align_left(sched_block)
        elif node.context_type == 'right':
            return pulse.transforms.align_right(sched_block)
        elif node.context_type == 'seq':
            return pulse.transforms.align_sequential(sched_block)

        raise Exception('Invalid alignment {type} is specified.'.format(type=node.context_type))
