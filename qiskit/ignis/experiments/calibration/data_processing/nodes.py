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
from qiskit.ignis.experiments.calibration.data_processing import base
from qiskit.ignis.experiments.calibration.data_processing.base import AnalysisStep
from qiskit.ignis.experiments.calibration.cal_metadata import CalibrationMetadata
from qiskit.result.counts import Counts


# kernels

@base.kernel
@base.prev_node()
class SystemKernel(AnalysisStep):
    """Backend system kernel."""
    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: CalibrationMetadata,
                shots: int):
        return data


# discriminators

@base.discriminator
@base.prev_node(SystemKernel)
class SystemDiscriminator(AnalysisStep):
    """Backend system discriminator."""
    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: CalibrationMetadata,
                shots: int):
        return data


# IQ data post-processing

@base.iq_data
@base.prev_node(SystemKernel)
class RealNumbers(AnalysisStep):
    """IQ data post-processing. This returns real part of IQ data."""
    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Union[float, np.ndarray],
                metadata: CalibrationMetadata,
                shots: int):
        return self.scale * data.real


@base.iq_data
@base.prev_node(SystemKernel)
class ImagNumbers(AnalysisStep):
    """IQ data post-processing. This returns imaginary part of IQ data."""
    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Any,
                metadata: CalibrationMetadata,
                shots: int):
        return self.scale * data.imag


# Count data post-processing

@base.counts
@base.prev_node(SystemDiscriminator)
class Population(AnalysisStep):
    """Count data post processing. This returns population."""

    def process(self,
                data: Counts,
                metadata: CalibrationMetadata,
                shots: int):

        populations = np.zeros(len(list(data.keys())[0]))

        for bit_str, count in data.items():
            for ind, bit in enumerate(bit_str):
                if bit == '1':
                    populations[ind] += count
        populations /= shots

        return populations
