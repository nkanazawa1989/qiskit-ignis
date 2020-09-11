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
"""
JSON serialization and deserialization
"""
# pylint: disable=missing-function-docstring, arguments-differ, method-hidden

import json
import numpy


class NumpyEncoder(json.JSONEncoder):
    """JSON Encoder for Numpy arrays and complex numbers."""

    _COMPLEX_DTYPE = ('complex', 'complex64', 'complex128')

    def default(self, obj):
        if isinstance(obj, numpy.ndarray):
            dtype = str(obj.dtype)
            if dtype in self._COMPLEX_DTYPE:
                value = [obj.real.tolist(), obj.imag.tolist()]
            else:
                value = obj.tolist()
            return {'type': 'array', 'dtype': dtype, 'value': value}
        if isinstance(obj, complex):
            return {'type': 'complex', 'value': [obj.real, obj.imag]}
        return super(NumpyEncoder, self).default(obj)


class NumpyDecoder(json.JSONDecoder):
    """JSON Decoder for Numpy arrays and complex numbers."""

    _COMPLEX_DTYPE = ('complex', 'complex64', 'complex128')

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if 'type' in obj:
            if obj['type'] == 'complex':
                val = obj['value']
                return val[0] + 1j * val[1]
            if obj['type'] == 'array':
                dtype = obj['dtype']
                value = obj['value']
                if dtype in self._COMPLEX_DTYPE:
                    ret = numpy.array(value[0], dtype=dtype)
                    ret.imag = value[1]
                    return ret
                return numpy.array(value, dtype=dtype)
        return obj
