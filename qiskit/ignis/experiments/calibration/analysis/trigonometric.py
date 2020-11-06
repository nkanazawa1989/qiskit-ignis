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

from scipy import signal
from typing import Iterator, Tuple, List

from qiskit.ignis.experiments.calibration.analysis.cal_1d_analysis import Calibration1DAnalysis


def _freq_guess(xvals: np.ndarray, yvals: np.ndarray):
    """Initial frequency guess for oscillating data."""

    fft_data = np.fft.fft(yvals)
    fft_freq = np.fft.fftfreq(len(xvals), xvals[1] - xvals[0])
    f0_guess = np.abs(fft_freq[np.argmax(np.abs(fft_data))])

    if f0_guess == 0:
        # sampling duration is shorter than oscillation period
        yvals = np.convolve(yvals, [0.5, 0.5], mode='same')
        peaks, = signal.argrelmin(yvals, order=int(len(xvals) / 4))
        if len(peaks) == 0 or len(peaks) > 4:
            return 0
        else:
            return 1 / (2 * xvals[peaks[0]])

    return f0_guess


class CosinusoidalFit(Calibration1DAnalysis):
    r"""Fit with $F(x) = a \cos(2\pi f x + \phi) + b$."""

    @classmethod
    def initial_guess(cls,
                      xvals: np.ndarray,
                      yvals: np.ndarray) -> Iterator[np.ndarray]:

        y_mean = np.mean(yvals)
        a0 = np.max(np.abs(yvals)) - np.abs(y_mean)
        f0 = max(0, _freq_guess(xvals, yvals))

        for phi in np.linspace(-np.pi, np.pi, 10):
            yield np.array([a0, f0, phi, y_mean])

    @classmethod
    def fit_function(cls, xvals: np.ndarray, *args) -> np.ndarray:
        return args[0] * np.cos(2 * np.pi * args[1] * xvals + args[2]) + args[3]

    @classmethod
    def fit_boundary(cls,
                     xvals: np.ndarray,
                     yvals: np.ndarray) -> Tuple[List[float], List[float]]:
        return [-np.inf, 0, -np.pi, -np.inf], [np.inf, np.inf, np.pi, np.inf]
