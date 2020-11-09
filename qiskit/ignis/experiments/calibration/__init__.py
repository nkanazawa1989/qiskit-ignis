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

"""
Qiskit Ignis calibration module.

Calibration1DAnalysis analyzes experiments in which one parameter is scanned.
The values of this parameter form the x_values. The experiment may have several
series which are interpreted as different curves. The x_values metadata for
each circuit should therefore be a dict with one entry and have the form
{parameter_name: parameter_value}.
"""

from qiskit.ignis.experiments.calibration.analysis.cal_1d_analysis import Calibration1DAnalysis
from qiskit.ignis.experiments.calibration.cal_table import PulseTable
from qiskit.ignis.experiments.calibration.mock import FakeSingleQubitTable
