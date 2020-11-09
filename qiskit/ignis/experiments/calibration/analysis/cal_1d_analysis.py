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

"""Qiskit Ignis calibration module."""

from collections import defaultdict
from typing import Union, Dict, Optional, Any, Iterator, List, Tuple

import numpy as np
from qiskit.result import Result, Counts
from scipy import optimize

from qiskit.ignis.experiments.base import Analysis
from qiskit.ignis.experiments.calibration import types
from qiskit.ignis.experiments.calibration.cal_metadata import CalibrationMetadata
from qiskit.ignis.experiments.calibration.workflow import AnalysisWorkFlow


class Calibration1DAnalysis(Analysis):
    """
    Calibration1DAnalysis analyzes experiments in which one parameter
    is scanned. The values of this parameter form the x_values.
    The experiment may have several series which are interpreted as
    different curves. The x_values metadata for each circuit should
    therefore be a dict with one entry and have the form
    {parameter_name: parameter_value}.
    """

    def __init__(self,
                 name: Optional[str] = None,
                 data: Optional[Any] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 exp_id: Optional[str] = None,
                 workflow: Optional[AnalysisWorkFlow] = None):
        """Initialize calibration experiment analysis

        Args:
            name: Name of this analysis.
            data: Result data to initialize with.
            metadata: Metadata to initialize with.
            exp_id: Experiment id string.
            workflow: the steps to process the data with.

        Additional Information:
            Pulse job doesn't return marginalized result.
            Result memory slot is marginalized with qubits specified in metadata.

            Users do not need to take care of data format.
            Data is automatically processed based on the give workflow.
        """
        # Workflow for measurement data processing
        self._workflow = workflow
        self._parameter = None
        self._series = {}
        self._x_values = None

        super().__init__(data=data,
                         metadata=metadata,
                         name=name,
                         exp_id=exp_id)

    @property
    def series(self):
        """Return data series dictionaries."""
        return self._series

    @property
    def x_values(self) -> list:
        """X-values of the data."""
        return self._x_values

    @property
    def workflow(self):
        """Return data processing routine."""
        return self._workflow

    @workflow.setter
    def workflow(self, work_flow: AnalysisWorkFlow):
        """Set workflow."""
        self._workflow = work_flow

    @classmethod
    def initial_guess(cls,
                      xvals: np.ndarray,
                      yvals: np.ndarray) -> Iterator[np.ndarray]:
        """Create initial guess for fit parameters.

        Args:
            xvals: Scanning parameter values.
            yvals: Measured outcomes.

        Yield:
            Set of initial guess for parameters.
            If multiple guesses are returned fit is performed for all parameter set.
            Error is measured by Chi squared value and the best fit result is chosen.

        Note:
            This should return values with yield rather than return.
        """
        raise NotImplementedError

    @classmethod
    def fit_boundary(cls,
                     xvals: np.ndarray,
                     yvals: np.ndarray) -> Tuple[List[float], List[float]]:
        """Returns boundary of parameters to fit."""
        raise NotImplementedError

    @classmethod
    def fit_function(cls, xvals: np.ndarray, *args) -> np.ndarray:
        """Fit function."""
        raise NotImplementedError

    def plot(self, ax: Optional['Axis'] = None, **kwargs) -> 'Figure':
        import matplotlib
        import matplotlib.pyplot as plt
        from matplotlib.pyplot import cm

        if ax:
            figure = ax.figure
        else:
            figure = plt.figure(figsize=kwargs.get('figsize', (6, 4)))
            ax = figure.add_subplot(111)

        xval_interp = np.linspace(self.x_values[0], self.x_values[-1], 100)

        idx = 0
        for series, yvals in self._series.items():
            yval_fit = self.fit_function(xval_interp, *self._result[series].fitval)
            ax.plot(xval_interp, yval_fit, '--', color=cm.tab20.colors[(2*idx+1) % cm.tab20.N])
            ax.plot(self.x_values, yvals, 'o', color=cm.tab20.colors[(2*idx) % cm.tab20.N])
            idx += 1

        ax.set_xlim(self.x_values[0], self.x_values[-1])

        ax.set_xlabel(kwargs.get('xlabel', kwargs.get('xlabel', 'Parameter')), fontsize=14)
        ax.set_ylabel(kwargs.get('ylabel', kwargs.get('ylabel', 'Signal')), fontsize=14)

        if matplotlib.get_backend() in ['module://ipykernel.pylab.backend_inline',
                                        'nbAgg']:
            plt.close(figure)

        return figure

    def run(self, **kwargs) -> any:
        """Analyze the stored data.

        Returns:
            any: the output of the analysis,
        """
        xvals, yvals = _create_data_vector(data=self.data,
                                           metadata_list=self.metadata)

        # fit for each initial guess
        result = None
        self._result = {}
        for series_key, yvals in yvals.items():
            for initial_guess in self.initial_guess(xvals, yvals):
                try:
                    p_opt, p_cov = optimize.curve_fit(self.fit_function,
                                                      xdata=xvals,
                                                      ydata=yvals,
                                                      p0=initial_guess,
                                                      bounds=self.fit_boundary(xvals, yvals))

                    # calculate chi square
                    chi_sq = _calculate_chisq(xvals=xvals,
                                              yvals=yvals,
                                              fit_yvals=self.fit_function(xvals, *p_opt),
                                              n_params=len(initial_guess))
                    # calculate standard deviation
                    stdev = np.sqrt(np.diag(p_cov))

                    if result is None or result.chisq > chi_sq:
                        result = types.FitResult(fitval=p_opt,
                                                 stdev=stdev,
                                                 chisq=chi_sq,
                                                 xvals=xvals,
                                                 yvals=yvals)

                # Fitting may fail. For now pass but perhaps log
                except RuntimeError:
                    pass

            # keep the best result
            self._series[series_key] = yvals
            self._result[series_key] = result

        self._x_values = xvals

        return self._result

    def _format_data(self,
                     data: Result,
                     metadata: Dict[str, any],
                     index: int) -> Counts:
        """Format the required data from a Result.data dict"""

        return self._workflow.format_data(
            result=data,
            metadata=metadata,
            index=index
        )


def _create_data_vector(data: List[np.ndarray],
                        metadata_list: List[Dict[str, any]],
                        ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """A helper function to extract xvalue and y value vectors from a set of
    data list and metadata.

    x values are returned as a list as this is a 1DCalibration analysis.
    y values are returned as a dictionary associated with each data series.

    Args:
        data: List of formatted data extracted from a Result class.
        metadata_list: List of metadata representing experimental condition.
            This should have the same length as data.

    Returns:
        x values and y values.
    """
    xvals = []
    yvals = defaultdict(list)

    for outcomes, meta in zip(data, metadata_list):
        metadata = CalibrationMetadata(**meta)
        xvals.append(next(iter(metadata.x_values.values())))

        # Single or averaged data
        if outcomes.size == 1:
            yvals[str(metadata.series)].append(outcomes[0])
        else:
            yvals[str(metadata.series)].append(outcomes)

    xvals = np.asarray(xvals, dtype=float)
    yvals = {key: np.asarray(val, dtype=float) for key, val in yvals.items()}

    return xvals, yvals


def _calculate_chisq(xvals: np.ndarray,
                     yvals: np.ndarray,
                     fit_yvals: np.ndarray,
                     n_params: int) -> float:
    """Calculate reduced Chi squared value.

    Args:
        xvals: X values.
        yvals: Y values.
        fit_yvals: Y values estimated from fit parameters.
        n_params: Number of fit parameters.
    """
    chi_sq = np.sum((fit_yvals - yvals) ** 2)
    dof = len(xvals) - n_params

    return chi_sq / dof
