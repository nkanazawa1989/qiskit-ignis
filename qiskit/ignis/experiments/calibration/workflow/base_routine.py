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
from typing import Any

from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class AnalysisRoutine(metaclass=ABCMeta):
    PREV_NODES = ()

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
        if not component.PREV_NODES:
            raise CalExpError('Analysis routine {name} is a root node. '
                              'This routine cannot be appended to another node.'
                              ''.format(name=component.__class__.__name__))

        if self._child is None:
            if isinstance(self, component.PREV_NODES):
                self._child = component
            else:
                raise CalExpError(
                    'Analysis routine {name} cannot be appended after {this}'
                    ''.format(name=component.__class__.__name__, this=self.__class__.__name__))
        else:
            self._child.append(component)

    @abstractmethod
    def process(self, data: Any, shots: int):
        pass

    def format_data(self, data: Any, shots: int):
        processed_data = self.process(data, shots)

        if self._child:
            return self._child.format_data(processed_data, shots)
        else:
            return processed_data
