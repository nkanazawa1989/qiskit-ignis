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

"""Utilities for database."""

import inspect
from typing import List

from qiskit import pulse, circuit


def get_pulse_parameters(pulse_shape: pulse.ParametricPulse) -> List[str]:
    """A helper function to extract a list of parameter names to construct the class.

    Args:
        pulse_shape: Parametric pulse subclass.

    Returns:
        List of parameter names except for `self` and `name`.
    """
    removes = ['self', 'name']

    init_signature = inspect.signature(pulse_shape.__init__)

    pnames = []
    for pname in init_signature.parameters.keys():
        if pname not in removes:
            pnames.append(pname)

    return pnames


def merge_duplicated_parameters(sched: pulse.Schedule) -> pulse.Schedule:
    """Merge duplicated parameters.

    This is mismatch of purpose of parameter object between QuantumCircuit and calibration.
    In QuantumCircuit, Parameter is always unique object even they have the same name.
    However, in calibration module parameters with the same name should be identical.
    """
    param_names = set(param.name for param in sched.parameters)

    marginalized_params = dict()
    for param_name in param_names:
        marginalized_params[param_name] = circuit.Parameter(param_name)

    bind_dict = {param: marginalized_params[param.name] for param in sched.parameters}

    return sched.assign_parameters(bind_dict)
