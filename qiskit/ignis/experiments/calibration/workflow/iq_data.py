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

from typing import Optional, Any

import numpy as np
from qiskit.ignis.experiments.calibration import workflow


class IQProcessing(workflow.AnalysisRoutine):
    PREV_NODES = (workflow.Kernel, )

    def process(self, data: Any, shots: int):
        raise NotImplementedError


class RealNumbers(IQProcessing):

    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self, data: Any, shots: int):
        data = np.asarray(data, dtype=complex)

        return self.scale * data.real


class ImagNumbers(IQProcessing):

    def __init__(self, scale: Optional[float] = 1.0):
        self.scale = scale
        super().__init__()

    def process(self, data: Any, shots: int):
        data = np.asarray(data, dtype=complex)

        return self.scale * data.imag
