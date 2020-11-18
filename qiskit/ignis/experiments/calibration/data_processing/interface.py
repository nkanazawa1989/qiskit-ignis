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
from qiskit.ignis.experiments.calibration.data_processing import (SystemKernel,
                                                                  SystemDiscriminator)
from qiskit.ignis.experiments.calibration.data_processing.base import NodeType, AnalysisStep
from qiskit.ignis.experiments.calibration.cal_metadata import CalibrationMetadata
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.qobj.utils import MeasLevel, MeasReturnType
from qiskit.result import Result
from qiskit.result.utils import marginal_counts


class DataProcessingSteps:
    """Definition of workflow of measurement data processing."""
    def __init__(self,
                 average: bool = True):
        """Create new workflow.

        Args:
            average: Set `True` to average outcomes.
        """
        self._average = average

        self._root_node = None
        self._shots = None

    @property
    def shots(self):
        """Return shot value."""
        return self._shots

    @shots.setter
    def shots(self, val: int):
        """Set new shot value."""
        self._shots = val

    def append(self, node: AnalysisStep):
        """Append new analysis node to this workflow."""
        if self._root_node:
            self._root_node.append(node)
        else:
            self._root_node = node

    def meas_return(self):
        """Return appropriate measurement format to execute this analysis chain."""
        if DataProcessingSteps.check_discriminator(self._root_node):
            # if discriminator is defined, return type should be single.
            # quantum state cannot be discriminated with averaged IQ coordinate.
            return MeasReturnType.SINGLE
        return MeasReturnType.AVERAGE if self._average else MeasReturnType.SINGLE

    def meas_level(self):
        """Return appropriate measurement level to execute this analysis chain."""
        kernel = DataProcessingSteps.check_kernel(self._root_node)
        if kernel and isinstance(kernel, SystemKernel):
            discriminator = DataProcessingSteps.check_discriminator(self._root_node)
            if discriminator and isinstance(discriminator, SystemDiscriminator):
                # classified level if both system kernel and discriminator are defined
                return MeasLevel.CLASSIFIED
            # kerneled level if only system kernel is defined
            return MeasLevel.KERNELED
        # otherwise raw level is requested
        return MeasLevel.RAW

    def format_data(self,
                    result: Result,
                    metadata: CalibrationMetadata,
                    index: int):
        """Format qiskit result data.

        This method sequentially calls stored child data processing nodes
        with its `format_data` methods. Once all child nodes have called,
        input data is converted into expected data format.

        Args:
            result: Qiskit Result object.
            metadata: Metadata for the target circuit.
            index: Index of target circuit in the experiment.
        """
        # extract outcome with marginalize. note that the pulse experiment data
        # is not marginalized on the backend.
        register_inds = [metadata.register_map[qind] for qind in metadata.qubits]
        if self.meas_level() == MeasLevel.CLASSIFIED:
            # Discriminated (count) data
            data = result.get_counts(experiment=index)
            marginal_data = marginal_counts(data, indices=register_inds)
        elif self.meas_level() == MeasLevel.KERNELED:
            # Kerneld (IQ) data
            data = np.asarray(result.get_memory(experiment=index), dtype=complex)
            if self._average:
                # averaged data
                marginal_data = np.zeros(len(register_inds), dtype=complex)
                for slot_ind, reg_ind in enumerate(register_inds):
                    marginal_data[slot_ind] = data[reg_ind]
            else:
                # single shot data
                marginal_data = np.zeros((self.shots, len(register_inds)), dtype=complex)
                for slot_ind, reg_ind in enumerate(register_inds):
                    marginal_data[:, slot_ind] = data[:, reg_ind]
        elif self.meas_level() == MeasLevel.RAW:
            # Raw data
            raise CalExpError('Raw data analysis is not supported.')
        else:
            raise CalExpError('Invalid measurement level is specified.')

        if not self._root_node:
            return marginal_data

        formatted_data = self._root_node.format_data(
            data=marginal_data,
            metadata=metadata,
            shots=self.shots
        )

        return formatted_data

    @classmethod
    def check_kernel(cls, node: AnalysisStep):
        """Return stored kernel in the workflow."""
        if node.node_type == NodeType.KERNEL:
            return node
        else:
            if not node.child:
                return None
            return cls.check_kernel(node.child)

    @classmethod
    def check_discriminator(cls, node: AnalysisStep):
        """Return stored discriminator in the workflow."""
        if node.node_type == NodeType.DISCRIMINATOR:
            return node
        else:
            if not node.child:
                return None
            return cls.check_discriminator(node.child)
