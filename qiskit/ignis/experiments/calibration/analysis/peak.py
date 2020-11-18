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

import numpy as np

from typing import Iterator, Tuple, List


from qiskit.ignis.experiments.calibration.cal_base_analysis import BaseCalibrationAnalysis


class GaussianFit(BaseCalibrationAnalysis):
    r"""Fit with $F(x) = a \exp(\frac{(x-x_0)^2}{2\sigma^2}) + b$."""

    def initial_guess(self,
                      xvals: np.ndarray,
                      yvals: np.ndarray) -> Iterator[np.ndarray]:
        y_mean = np.mean(yvals)
        peak_pos = np.argmax(np.abs(yvals - y_mean))
        x_peak = xvals[peak_pos]
        y_peak = yvals[peak_pos]
        y_fwhm = np.where(yvals - y_mean > 0.5 * y_peak, xvals, np.nan)
        x0 = np.nanargmin(y_fwhm)
        x1 = np.nanargmax(y_fwhm)

        yield np.array([y_peak - y_mean, x_peak, x1 - x0, y_mean])

    def fit_function(self, xvals: np.ndarray, *args) -> np.ndarray:
        return args[0] * np.exp(-(xvals - args[1])**2/(2 * args[2]**2)) + args[3]

    def fit_boundary(self,
                     xvals: np.ndarray,
                     yvals: np.ndarray) -> List[Tuple[float, float]]:

        return [(-np.inf, np.inf), (-np.inf, np.inf), (0, np.inf), (-np.inf, np.inf)]
