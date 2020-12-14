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

"""Helper methods to extract data from the fits."""

import numpy as np

from qiskit.ignis.experiments.calibration.cal_base_analysis import BaseCalibrationAnalysis
from qiskit.ignis.experiments.calibration.analysis.trigonometric import CosinusoidalFit


def get_period_fraction(analysis: BaseCalibrationAnalysis, angle: float,
                        qubit: int, tag: str) -> float:
    """
    Returns the x location corresponding to a given rotation angle. E.g.
    if angle = pi and the function function is cos(2 pi a x) then return pi/2*pi*a.
    Not all analysis routines will implement this.

    Args:
        analysis: The analysis routing from which to retrieve a periodicity.
        angle: The desired rotation angle.
        qubit: the qubit for which the analysis was carried out.
        tag: the key used to identify the fit in self.result.
    """

    if isinstance(analysis, CosinusoidalFit):
        return angle / (2*np.pi*analysis.result[qubit][tag].fitvals[1])

    raise NotImplementedError
