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

from typing import Optional, Any, Dict, Union

import numpy as np

from qiskit.ignis.experiments.calibration import workflow
from qiskit.result.counts import Counts
from qiskit.result.utils import marginal_counts


# root node

@workflow.root
class Marginalize(workflow.AnalysisRoutine):
    """Remove redundant memory slot from the result."""
    def process(self,
                data: Union[Counts, np.ndarray],
                metadata: Dict[str, Any],
                shots: int):
        """Process input data."""
        if 'qubits' in metadata:
            qinds = list(range(len(metadata['qubits'])))
            if isinstance(data, Counts):
                # count dictionary
                marginal_data = marginal_counts(data, indices=qinds)
            else:
                # IQ data
                if len(data.shape) > 1:
                    # single shot
                    marginal_data = np.zeros((data.shape[0], len(qinds)), dtype=complex)
                    for slot_ind, qind in enumerate(qinds):
                        marginal_data[:, slot_ind] = data[:, qind]
                else:
                    # averaged
                    marginal_data = np.zeros(len(qinds), dtype=complex)
                    for slot_ind, qind in enumerate(qinds):
                        marginal_data[slot_ind] = data[qind]
        else:
            marginal_data = data

        return marginal_data


# kernels

@workflow.kernel
@workflow.prev_node(Marginalize)
class SystemKernel(workflow.AnalysisRoutine):
    """Backend system kernel."""
    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        return data


# discriminators

@workflow.discriminator
@workflow.prev_node(SystemKernel)
class SystemDiscriminator(workflow.AnalysisRoutine):
    """Backend system discriminator."""
    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        return data


# IQ data post-processing

@workflow.iq_data
@workflow.prev_node(SystemKernel)
class RealNumbers(workflow.AnalysisRoutine):
    """IQ data post-processing. This returns real part of IQ data."""
    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Union[float, np.ndarray],
                metadata: Dict[str, Any],
                shots: int):
        return self.scale * data.real


@workflow.iq_data
@workflow.prev_node(SystemKernel)
class ImagNumbers(workflow.AnalysisRoutine):
    """IQ data post-processing. This returns imaginary part of IQ data."""
    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[float, np.ndarray],
                shots: int):
        return self.scale * data.imag


# Counts

@workflow.counts
@workflow.prev_node(SystemDiscriminator)
class Population(workflow.AnalysisRoutine):
    """Count data post processing. This returns population."""

    def process(self,
                data: Counts,
                metadata: Dict[float, np.ndarray],
                shots: int):

        populations = np.zeros(len(list(data.keys())[0]))

        for bit_str, count in data.items():
            for ind, bit in enumerate(bit_str):
                if bit == '1':
                    populations[ind] += count
        populations /= shots

        return populations
