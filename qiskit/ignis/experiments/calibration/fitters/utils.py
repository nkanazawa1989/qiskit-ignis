# -*- coding: utf-8 -*-

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


from typing import Dict, Any, Tuple, Union, List, Optional
from collections import defaultdict

import numpy as np


def create_data_vector(data: List[np.ndarray],
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

    for data, meta in zip(data, metadata):
        if parameter:
            xvals.append(meta.get(parameter, None))
        if series:
            for sind, sub_meta in enumerate(series):
                if _check_series(meta=meta, sub_meta=sub_meta):
                    if data.size == 1:
                        yvals[sind].append(data[0])
                    else:
                        yvals[sind].append(data)
        else:
            yvals[0].append(data)

    xvals = np.asarray(xvals, dtype=float)

    if len(yvals) == 1:
        yvals = np.asarray(yvals[0], dtype=float)
    else:
        yvals = {sind: np.asarray(yval, dtype=float) for sind, yval in yvals.items()}

    return xvals, yvals


def calculate_chisq(xvals: np.ndarray,
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
