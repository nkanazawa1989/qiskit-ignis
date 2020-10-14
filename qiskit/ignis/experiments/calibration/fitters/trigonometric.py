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

from typing import List, Dict, Any

from scipy import optimize, signal
from numpy import np

from qiskit.ignis.experiments.calibration import fitters, types
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


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


def fit_cosinusoidal(data: np.ndarray,
                     metadata: List[Dict[str, Any]],
                     parameter: str,
                     series: List[Dict[str, Any]]) -> types.FitResult:
    """Perform cosinusoidal fit.

    Args:
        data: Formatted data to fit.
        metadata: List of metadata representing experimental configuration of each data entry.
        parameter: Name of parameter to scan.
        series: Partial dictionary to represent a series of experiment.

    Returns:
        Fit parameters with statistics.
    """

    if series:
        raise CalExpError('Sinusoidal fit does not take multiple data series. '
                          'Check your experiment configuration.')

    xvals, yvals = fitters.create_data_vector(data=data,
                                              metadata=metadata,
                                              parameter=parameter,
                                              series=series)

    def fit_function(x, amp, freq, phase, offset):
        return amp * np.cos(2 * np.pi * freq * x + phase) + offset

    # create initial guess of parameters
    amp0 = np.max(np.abs(yvals))
    freq0 = _freq_guess(xvals, yvals)
    phase0 = 0
    offset0 = 0
    initial_guess = np.array([amp0, freq0, phase0, offset0])

    p_opt, p_cov = optimize.curve_fit(fit_function, xvals, yvals, p0=initial_guess)
    chi_sq = fitters.calculate_chisq(xvals=xvals,
                                     yvals=yvals,
                                     fit_yvals=fit_function(xvals, *p_opt),
                                     n_params=4)
    stdevs = np.sqrt(np.diag(p_cov))

    return types.FitResult(fitval=p_opt, stdev=stdevs, chisq=chi_sq)
