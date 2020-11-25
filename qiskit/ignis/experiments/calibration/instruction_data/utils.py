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
import re
from typing import Dict, List

from qiskit import pulse


def composite_param_name(name: str, channel: str, pulse_name: str) -> str:
    """Embed pulse information to parameter name.

    Args:
        name: Name of parameter.
        channel: Name of channel that the pulse associated with the parameter belongs to.
        pulse_name: Name of the pulse associated with the parameter.

    Returns:
          Name of parameter in local scope.
    """
    return '{}.{}.{}'.format(pulse_name, channel, name)


def split_param_name(param_name: str) -> Dict[str, str]:
    """Remove pulse information from parameter name.

    Args:
        param_name: Scoped name of parameter.

    Returns:
          Name of parameter with scope.
    """
    name_regex = r'(?P<pulse>(\w+)).(?P<chan>([a-zA-Z]+)(\d+)).(?P<name>(\w+))'

    matched = re.match(name_regex, param_name)
    if matched:
        return {
            'name': matched.group('name'),
            'channel': matched.group('chan'),
            'pulse_name': matched.group('pulse')
        }

    raise Exception('Invalid parameter name {pname}'.format(pname=param_name))


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
