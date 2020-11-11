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
import numpy as np
from typing import Dict, Union


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
                (0, 1): TwoQubitPulse(channel='d1', amp=0.02, phase=0.2),
                (1, 0): TwoQubitPulse(channel='d0', amp=0.03, phase=0.2)
            },
            'cr90m_d': {
                (0, 1): TwoQubitPulse(channel='d1', amp=0.02, phase=0.2 + np.pi),
                (1, 0): TwoQubitPulse(channel='d0', amp=0.03, phase=0.2 + np.pi)
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
