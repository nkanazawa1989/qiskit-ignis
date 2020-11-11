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

"""Special data types for calibration module."""

from enum import Enum
from typing import List, Dict, Any, Union, NewType, NamedTuple

import numpy as np
import pandas as pd
from qiskit.circuit import QuantumCircuit, Parameter

# All data types that can be accepted as parameter
ParamValue = NewType('ParamValue', Union[int, float, Parameter])

# Set of circuit and metadata
CalProg = NamedTuple(
    'CalProg',
    [('circuits', List[QuantumCircuit]),
     ('metadata', List[Dict[str, Any]])]
)
CalProg.__doc__ = 'Set of circuit and associated metadata.'
CalProg.circuits.__doc__ = 'List of calibration circuit.'
CalProg.metadata.__doc__ = 'List of metadata representing experimental details.'

CalValue = NamedTuple(
    'CalValue',
    [('value', Union[int, float, complex]),
     ('validation', str),
     ('timestamp', pd.Timestamp)]
)
CalValue.__doc__ = 'Calibrated value with timestamp and status of validation.'
CalValue.value.__doc__ = 'Value'
CalValue.validation.__doc__ = 'Calibration data validation status.'
CalValue.timestamp.__doc__ = 'Time information of when this value is created.'


# Fit result
FitResult = NamedTuple(
    'FitResult',
    [('fitval', List[float]),
     ('stdev', List[float]),
     ('chisq', float),
     ('xvals', np.ndarray),
     ('yvals', np.ndarray)]
)
FitResult.__doc__ = 'Result data of fitting.'
FitResult.fitval.__doc__ = 'Fit parameter values.'
FitResult.stdev.__doc__ = 'Standard deviation of fit parameters.'
FitResult.chisq.__doc__ = 'Reduced Chi squared value of fit result.'


class SingleQubitPulses(Enum):
    """Name of single qubit gates."""
    X90P = 'x90p'
    X90M = 'x90m'
    Y90P = 'y90p'
    Y90M = 'y90m'
    XP = 'xp'
    XM = 'xm'
    YP = 'yp'
    YM = 'ym'
    STIM = 'stimulus'


class ValidationStatus(Enum):
    PASS = 'pass'
    FAIL = 'fail'
    NONE = 'none'
