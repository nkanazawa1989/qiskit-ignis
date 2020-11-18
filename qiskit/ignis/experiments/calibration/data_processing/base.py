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
"""Definition of sub routine of data processing.

AnalysisStep represents a node of the data analysis tree that specifies what
operations are performed on the data such as taking the real part of complex data
or scaling the data. This data processing chain is represented as a tree,
and this will also provide correct execution options that are consistent with data processing.
"""

from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Any

from qiskit.ignis.experiments.calibration.cal_metadata import CalibrationMetadata
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class AnalysisStep(metaclass=ABCMeta):
    node_type = None
    prev_node = ()

    def __init__(self):
        """Create new data analysis routine.
        """
        self._child = None

    @property
    def child(self):
        return self._child

    def append(self, component: 'AnalysisStep'):
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
                metadata: CalibrationMetadata,
                shots: int):
        raise NotImplementedError

    def format_data(self,
                    data: Any,
                    metadata: CalibrationMetadata,
                    shots: int):
        processed_data = self.process(data, metadata, shots)

        if self._child:
            return self._child.format_data(processed_data, metadata, shots)
        else:
            return processed_data


class NodeType(Enum):
    KERNEL = 1
    DISCRIMINATOR = 2
    IQDATA = 3
    COUNTS = 4


def kernel(cls: AnalysisStep):
    """A decorator to give kernel attribute to node."""
    cls.node_type = NodeType.KERNEL
    return cls


def discriminator(cls: AnalysisStep):
    """A decorator to give discriminator attribute to node."""
    cls.node_type = NodeType.DISCRIMINATOR
    return cls


def iq_data(cls: AnalysisStep):
    """A decorator to give iqdata attribute to node."""
    cls.node_type = NodeType.IQDATA
    return cls


def counts(cls: AnalysisStep):
    """A decorator to give counts attribute to node."""
    cls.node_type = NodeType.COUNTS
    return cls


def prev_node(*nodes: AnalysisStep):
    """A decorator to specify the available previous nodes."""

    try:
        nodes = list(nodes)
    except TypeError:
        nodes = [nodes]

    def add_nodes(cls: AnalysisStep):
        cls.prev_node = tuple(nodes)
        return cls

    return add_nodes
