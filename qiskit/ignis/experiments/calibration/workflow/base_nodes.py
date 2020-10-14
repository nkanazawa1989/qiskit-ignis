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
"""

"""

from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Any, Dict

from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class AnalysisRoutine(metaclass=ABCMeta):
    node_type = None
    prev_node = ()

    def __init__(self):
        """Create new workflow."""
        self._child = None

    @property
    def child(self):
        return self._child

    def append(self, component: 'AnalysisRoutine'):
        """Add new data processing routine.

        Args:
            component: New data processing routine.
        """
        if not component.prev_node:
            raise CalExpError('Analysis routine {name} is a root node. '
                              'This routine cannot be appended to another node.'
                              ''.format(name=component.__class__.__name__))

        if self._child is None:
            if isinstance(self, component.prev_node):
                self._child = component
            else:
                raise CalExpError(
                    'Analysis routine {name} cannot be appended after {this}'
                    ''.format(name=component.__class__.__name__, this=self.__class__.__name__))
        else:
            self._child.append(component)

    @abstractmethod
    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        pass

    def format_data(self,
                    data: Any,
                    metadata: Dict[str, Any],
                    shots: int):
        processed_data = self.process(data, metadata, shots)

        if self._child:
            return self._child.format_data(processed_data, metadata, shots)
        else:
            return processed_data


class NodeType(Enum):
    ROOT = 0
    KERNEL = 1
    DISCRIMINATOR = 2
    IQDATA = 3
    COUNTS = 4


def root(cls: AnalysisRoutine):
    """A decorator to give root attribute to node."""
    cls.node_type = NodeType.ROOT
    return cls


def kernel(cls: AnalysisRoutine):
    """A decorator to give kernel attribute to node."""
    cls.node_type = NodeType.KERNEL
    return cls


def discriminator(cls: AnalysisRoutine):
    """A decorator to give discriminator attribute to node."""
    cls.node_type = NodeType.DISCRIMINATOR
    return cls


def iq_data(cls: AnalysisRoutine):
    """A decorator to give iqdata attribute to node."""
    cls.node_type = NodeType.IQDATA
    return cls


def counts(cls: AnalysisRoutine):
    """A decorator to give counts attribute to node."""
    cls.node_type = NodeType.COUNTS
    return cls


def prev_node(*nodes: AnalysisRoutine):
    """A decorator to specify the available previous nodes."""

    try:
        nodes = list(nodes)
    except TypeError:
        nodes = [nodes]

    def add_nodes(cls: AnalysisRoutine):
        cls.prev_node = tuple(nodes)
        return cls

    return add_nodes
