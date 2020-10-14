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

from typing import Dict, Any
import numpy as np

from qiskit.ignis.experiments.calibration import workflow
from qiskit.ignis.experiments.calibration.workflow.base_routine import NodeType
from qiskit.qobj.utils import MeasLevel, MeasReturnType
from qiskit.result import Result


class AnalysisWorkFlow:
    """Definition of workflow of measurement data processing."""
    def __init__(self,
                 average: bool = True):
        """Create new workflow.

        Args:
            qubits: Set index of qubits to extract.
            average: Set `True` to average outcomes.
        """
        self._root_node = workflow.Marginalize()
        self._shots = None

        self._average = average

    @property
    def shots(self):
        """Return shot value."""
        return self._shots

    @shots.setter
    def shots(self, val: int):
        """Set new shot value."""
        self._shots = val

    def append(self, node: workflow.AnalysisRoutine):
        """Append new analysis node to this workflow."""
        self._root_node.append(node)

    def meas_return(self):
        """Return appropriate measurement format to execute this analysis chain."""
        if AnalysisWorkFlow.check_discriminator(self._root_node):
            # if discriminator is defined, return type should be single.
            # quantum state cannot be discriminated with averaged IQ coordinate.
            return MeasReturnType.SINGLE
        return MeasReturnType.AVERAGE if self._average else MeasReturnType.SINGLE

    def meas_level(self):
        """Return appropriate measurement level to execute this analysis chain."""
        kernel = AnalysisWorkFlow.check_kernel(self._root_node)
        if kernel and isinstance(kernel, workflow.SystemKernel):
            discriminator = AnalysisWorkFlow.check_discriminator(self._root_node)
            if discriminator and isinstance(discriminator, workflow.SystemDiscriminator):
                # classified level if both system kernel and discriminator are defined
                return MeasLevel.CLASSIFIED
            # kerneled level if only system kernel is defined
            return MeasLevel.KERNELED
        # otherwise raw level is requested
        return MeasLevel.RAW

    def format_data(self,
                    result: Result,
                    metadata: Dict[str, Any],
                    index: int):
        """Format qiskit result data."""
        if not self._root_node:
            return result

        if self.meas_level() == MeasLevel.CLASSIFIED:
            data = result.get_counts(experiment=index)
        else:
            data = np.asarray(result.get_memory(experiment=index), dtype=complex)

        formatted_data = self._root_node.format_data(
            data=data,
            metadata=metadata,
            shots=self.shots
        )

        return formatted_data

    @classmethod
    def check_kernel(cls, node: workflow.AnalysisRoutine):
        """Return stored kernel in the workflow."""
        if node.node_type == NodeType.KERNEL:
            return node
        else:
            if not node.child:
                return None
            return cls.check_kernel(node.child)

    @classmethod
    def check_discriminator(cls, node: workflow.AnalysisRoutine):
        """Return stored discriminator in the workflow."""
        if node.node_type == NodeType.DISCRIMINATOR:
            return node
        else:
            if not node.child:
                return None
            return cls.check_discriminator(node.child)
