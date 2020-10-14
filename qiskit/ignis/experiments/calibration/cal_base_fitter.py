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
from qiskit.circuit import Parameter
from qiskit.result import Result, Counts
from scipy import optimize

from qiskit.ignis.experiments.base import Analysis
from qiskit.ignis.experiments.calibration import types
from qiskit.ignis.experiments.calibration.workflow import AnalysisWorkFlow


class BaseCalibrationAnalysis(Analysis):
    """Calibration experiment analysis."""

    def __init__(self,
                 name: Optional[str] = None,
                 data: Optional[Any] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 exp_id: Optional[str] = None):
        """Initialize calibration experiment analysis

        Args:
            name: Name of this analysis.
            data: Result data to initialize with.
            metadata: Metadata to initialize with.
            exp_id: Experiment id string.

        Additional Information:
            Pulse job doesn't return marginalized result.
            Result memory slot is marginalized with qubits specified in metadata.

            User don't need to take care of data format.
            Data is automatically processed based on the give workflow.
        """
        # Workflow for measurement data processing
        self._workflow = None
        self._parameter = None
        self._series = []

        super().__init__(data=data,
                         metadata=metadata,
                         name=name,
                         exp_id=exp_id)

    @property
    def series(self):
        """Return data series dictionaries."""
        return self._series

    @series.setter
    def series(self, new_series: Dict[str, Any]):
        """Add new data series."""
        self._series.append(new_series)

    @property
    def parameter(self):
        """Return parameter to scan."""
        return self._parameter

    @parameter.setter
    def parameter(self, parameter: Union[Parameter, str]):
        """Add new parameter."""
        if isinstance(parameter, Parameter):
            self._parameter = parameter.name
        else:
            self._parameter = parameter

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

        if ax:
            figure = ax.figure
        else:
            figure = plt.figure(figsize=kwargs.get('figsize', (6, 4)))
            ax = figure.add_subplot(111)

        xval_interp = np.linspace(self._result.xvals[0], self._result.xvals[-1], 100)
        yval_fit = self.fit_function(xval_interp, *self._result.fitval)

        ax.plot(xval_interp, yval_fit, '--', color='blue')
        ax.plot(self._result.xvals, self._result.yvals, 'o', color='blue')

        ax.set_xlim(self._result.xvals[0], self._result.xvals[-1])

        ax.set_xlabel(kwargs.get('xlabel', self.parameter), fontsize=14)
        ax.set_ylabel(kwargs.get('ylabel', 'Signal'), fontsize=14)

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
                                           metadata=self.metadata,
                                           parameter=self.parameter,
                                           series=self.series)

        # fit for each initial guess
        result = None
        for initial_guess in self.initial_guess(xvals, yvals):
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

        # keep the best result
        self._result = result

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
                        metadata: List[Dict[str, Any]],
                        parameter: Optional[str] = None,
                        series: Optional[List[Dict[str, Any]]] = None
                        ) -> Tuple[np.ndarray, Union[np.ndarray, Dict[int, np.ndarray]]]:
    """A helper function to extract xvalue and y value vectors from a set of
    data list and metadata.

    If multiple series labels are provided, y values are returned as a dictionary
    associated with each data series.

    Args:
        data: List of formatted data.
        metadata: List of metadata representing experimental condition.
        parameter: Name of parameter to scan.
        series: Partial dictionary to represent a subset of experiment.

    Returns:
        Data vectors of scanning parameters and outcomes.
    """
    xvals = []
    yvals = defaultdict(list)

    def _check_series(meta: Dict[str, Any], sub_meta: Dict[str, Any]):
        for key, val in sub_meta.items():
            if meta[key] != val:
                return False
        return True

    for outcomes, meta in zip(data, metadata):
        if parameter:
            xvals.append(meta.get(parameter, None))
        if series:
            for sind, sub_meta in enumerate(series):
                if _check_series(meta=meta, sub_meta=sub_meta):
                    if outcomes.size == 1:
                        yvals[sind].append(outcomes[0])
                    else:
                        yvals[sind].append(outcomes)
        else:
            if outcomes.size == 1:
                yvals[0].append(outcomes[0])
            else:
                yvals[0].append(outcomes)

    xvals = np.asarray(xvals, dtype=float)

    if len(yvals) == 1:
        yvals = np.asarray(yvals[0], dtype=float)
    else:
        yvals = {sind: np.asarray(yval, dtype=float) for sind, yval in yvals.items()}

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
