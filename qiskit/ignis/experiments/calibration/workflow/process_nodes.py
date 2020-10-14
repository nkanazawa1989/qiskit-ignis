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


# root node

@workflow.root
class Marginalize(workflow.AnalysisRoutine):

    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        """Process input data."""
        pass


# kernels

@workflow.kernel
@workflow.prev_node(Marginalize)
class SystemKernel(workflow.AnalysisRoutine):

    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        pass


# discriminators

@workflow.discriminator
@workflow.prev_node(SystemKernel)
class SystemDiscriminator(workflow.AnalysisRoutine):

    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[str, Any],
                shots: int):
        pass


# IQ data post-processing

@workflow.iq_data
@workflow.prev_node(SystemKernel)
class RealNumbers(workflow.AnalysisRoutine):

    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Union[float, np.ndarray],
                metadata: Dict[str, Any],
                shots: int):
        return data.real


@workflow.iq_data
@workflow.prev_node(SystemKernel)
class ImagNumbers(workflow.AnalysisRoutine):

    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self,
                data: Any,
                metadata: Dict[float, np.ndarray],
                shots: int):
        return data.imag
