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

from qiskit.ignis.experiments.calibration import workflow


class Kernel(workflow.AnalysisRoutine):
    PREV_NODES = ()

    def process(self, data: Any, shots: int):
        return data


class SystemKernel(Kernel):
    PREV_NODES = ()

    def __init__(self, name: Optional[str] = None):
        self.name = name
        super().__init__()
