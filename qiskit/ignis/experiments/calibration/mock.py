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

"""Mock database."""

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable
from qiskit.result import Result
import numpy as np
from typing import Dict, Union

import datetime


@dataclass(frozen=True)
class SingleQubitPulse:
    channel: str = 'd0'
    shape: str = 'drag'
    duration: int = 160
    amp: float = 0.04
    phase: float = 0
    sigma: float = 40
    beta: float = 1.5
    timestamp: pd.Timestamp = pd.Timestamp('2020-01-01 00:00:00')

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """Return parameters as dictionary.

        Returns:
            Dictionary of parameters.
        """
        return {'duration': self.duration,
                'amp': self.amp,
                'phase': self.phase,
                'sigma': self.sigma,
                'beta': self.beta}


@dataclass(frozen=True)
class TwoQubitPulse:
    channel: str = 'u0'
    shape: str = 'gaussian_square'
    duration: int = 800
    amp: float = 0.05
    phase: float = 0
    sigma: float = 128
    width: float = 544
    timestamp: pd.Timestamp = pd.Timestamp('2020-01-01 00:00:00')

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """Return parameters as dictionary.

        Returns:
            Dictionary of parameters.
        """
        return {'duration': self.duration,
                'amp': self.amp,
                'phase': self.phase,
                'sigma': self.sigma,
                'width': self.width}


class FakeTwoQubitParameters(PulseTable):
    """Mock pulse table database of two qubit system.

    This system consists of x90p, x90m, y90p and cross resonance pulse from qubit0 to 1.
    This configuration conforms to the typical IBM Quantum backend.
    """
    def __init__(self):
        """Create new mock data base."""

        instructions = {
            'x90p': {
                (0, ): SingleQubitPulse(channel='d0', amp=0.04),
                (1, ): SingleQubitPulse(channel='d1', amp=0.05)
            },
            'x90m': {
                (0, ): SingleQubitPulse(channel='d0', amp=0.04, phase=np.pi),
                (1, ): SingleQubitPulse(channel='d1', amp=0.05, phase=np.pi)
            },
            'y90p': {
                (0, ): SingleQubitPulse(channel='d0', amp=0.04, phase=np.pi / 2),
                (1, ): SingleQubitPulse(channel='d1', amp=0.05, phase=np.pi / 2)
            },
            'xp': {
                (0, ): SingleQubitPulse(channel='d0', amp=0.08),
                (1, ): SingleQubitPulse(channel='d1', amp=0.10)
            },
            'cr90p_u': {
                (0, 1): TwoQubitPulse(channel='u0', amp=0.05),
                (1, 0): TwoQubitPulse(channel='u1', amp=0.08),
            },
            'cr90m_u': {
                (0, 1): TwoQubitPulse(channel='u0', amp=0.05, phase=np.pi),
                (1, 0): TwoQubitPulse(channel='u1', amp=0.08, phase=np.pi),
            },
            'cr90p_d': {
                (1, ): TwoQubitPulse(channel='d1', amp=0.02, phase=0.2),
                (0, ): TwoQubitPulse(channel='d0', amp=0.03, phase=0.2)
            },
            'cr90m_d': {
                (1, ): TwoQubitPulse(channel='d1', amp=0.02, phase=0.2 + np.pi),
                (0, ): TwoQubitPulse(channel='d0', amp=0.03, phase=0.2 + np.pi)
            }
        }

        fake_table = defaultdict(list)
        for inst_name, qubit_table in instructions.items():
            for qubits, parameter_data in qubit_table.items():
                for pname, pval in parameter_data.to_dict().items():
                    fake_table['qubits'].append(tuple(qubits))
                    fake_table['channel'].append(parameter_data.channel)
                    fake_table['inst_name'].append(inst_name)
                    fake_table['stretch_factor'].append(1.0)
                    fake_table['pulse_type'].append(parameter_data.shape)
                    fake_table['name'].append(pname)
                    fake_table['value'].append(pval)
                    fake_table['validation'].append('pass')
                    fake_table['timestamp'].append(parameter_data.timestamp)

        super().__init__(params_collection=pd.DataFrame(data=fake_table))


def create_fake_rabi_experiment_result(
        target_qubit: int,
        amps: np.ndarray,
        fit_args: np.ndarray,
        iq_phase: float,
        data_slot: int,
        n_qubits: int,
        exp_id: str) -> Result:
    """Create fake experimental result of rough amplitude calibration.

    Experimental results are generated based on fitting parameters and this enables us to
    test functionality of entire analysis module by comparing the fit result and
    input fitting parameters. The measurement result is kerneled (`meas_level=1`) and
    averaged (`meas_return='avg'`). `qobj_id` and `job_id` are random strings.

    Args:
        target_qubit: Index of target qubit.
        amps: Array of pulse amplitudes.
        fit_args: Fit parameters. This conforms to the fit function of
            :py:class:~`qiskit.ignis.experiments.calibration.analysis.CosinusoidalFit`.
        iq_phase: IQ phase of the measure centroid on the IQ plane.
        data_slot: Index of data slot where measurement data is stored.
        n_qubits: Number of qubit in this system.
        exp_id: Strings representing the experimental ID. This is usually generated
            by the Ignis experiment class.
    """
    # create fake data with kerneled and averaged.
    results = []
    for amp in amps:
        data = np.zeros(n_qubits, dtype=complex)
        iq_amp = fit_args[0] * np.cos(2 * np.pi * fit_args[1] * amp + fit_args[2]) + fit_args[3]
        data[data_slot] = iq_amp * np.exp(1j * iq_phase)
        result_dict = {
            'shots': 1024,
            'success': True,
            'data': {'memory': list(map(list, np.vstack((data.real, data.imag)).T))},
            'meas_level': 1,
            'header': {'memory_slots': n_qubits, 'name': 'rough_amplitude'},
            'meas_return': 'avg'
        }
        results.append(result_dict)

    # create fake metadata
    metadata = []
    for amp in amps:
        meta_dict = {
            'name': 'rough_amplitude',
            'register_map': {target_qubit: data_slot},
            'series': 'single_pulse',
            'x_values': {'x90p.d{:d}.drag.amp'.format(target_qubit): amp},
            'pulse_schedule_name': 'SinglePulseGenerator',
            'exp_id': exp_id,
            'qubits': [target_qubit]
        }
        metadata.append(meta_dict)

    result_data = {
        'backend_name': 'fake_ignis_backend',
        'backend_version': '1.0.0',
        'qobj_id': '986b3c40-c56d-4998-9adc-3e59c08d22f7',
        'job_id': 'b802a247536c4fd2b9b0a0c3c2509987',
        'success': True,
        'results': results,
        'date': datetime.datetime(2020, 1, 1, 0, 0, 0),
        'status': 'Successful completion',
        'header': {
            'backend_name': 'fake_ignis_backend',
            'backend_version': '1.0.0',
            'metadata': metadata
        }
    }

    return Result.from_dict(result_data)
