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
from enum import Enum
from typing import List, Dict, NamedTuple, Iterator, Any, Union, Tuple

from qiskit import pulse


class TokenSpec(Enum):
    """Defined syntax of calibration schedule DSL.

    The enum name is the AST node type, the value is its mapping to the DSL syntax.
    """
    CONTEXT_ENTER = r'\[(?P<pos>right|left|seq)\]{'
    CONTEXT_EXIT = r'}'
    REFERENCE = r'&(?P<name>[\w]*)'
    PULSE = r'%(?P<name>[\w]*)\((?P<channel>[a-z][0-9]+),(?P<shape>[\w]*)\)'


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
class AuxInst(Inst):
    """A leaf that represents non-pulse schedule component such as frame change."""
    channel: str
    operands: Tuple[Any]

    def __repr__(self):
        return 'Aux({},{})'.format(self.name, ','.join(map(str, self.operands)))


@dataclasses.dataclass(frozen=True)
class Reference(Inst):
    """A leaf that represents a reference to another schedule definition."""

    def __repr__(self):
        return 'Reference({})'.format(self.name)


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
        if token.type in [TokenSpec.PULSE.name, TokenSpec.REFERENCE.name]:
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
        self.pulse_table = None
        self.sched_table = None
        self.id = None
        self.shape_map = ParametricPulseShapes
        self.channel_map = ChannelPrefixes

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
        query = (node.name, node.channel, self.id)
        played_pulse = self.shape_map[node.shape](**self.pulse_table.get_kwargs(*query))
        channel = self._get_channel(node.channel)

        return pulse.Play(played_pulse, channel)

    def visit_AuxInst(self, node: AuxInst):
        """Evaluate non-pulse instruction node and return non-pulse instruction.

        Args:
            node: AuxInst node to evaluate.

        Returns:
            Arbitrary non-pulse instruction specified by AST name.
        """
        raise NotImplementedError

    def visit_Reference(self, node: Reference):
        """Evaluate reference node and return arbitrary schedule.

        Args:
            node: Reference node to evaluate.

        Returns:
            Arbitrary schedule from another schedule database entry.
        """
        return self.sched_table.get(node.name)

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
