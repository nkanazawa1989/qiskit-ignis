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

import pandas as pd
from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable


class FakeSingleQubitTable(PulseTable):
    """Fake parameter table. For debugging and unittest purposes."""
    GATE_TYPES = ['x90p', 'xp']

    def __init__(self,
                 n_qubits: int,
                 default_duration: int = 160,
                 default_amp: float = 0.08,
                 default_phase: float = 0,
                 default_sigma: float = 40.,
                 default_beta: float = 1.5,
                 caldate: str = '2020-01-01 00:00:00'):
        """Create new parameter table.

        Args:
            n_qubits: Number of qubits in this system.
            default_duration: Duration of single qubit gates.
            default_amp: Amplitude of single qubit gates.
            default_phase: Phase of single qubit gates.
            default_sigma: Gaussian sigma of single qubit gates.
            default_beta: DRAG beta of single qubit gates.
            caldate: Date of when those parameters are acquired.

       Notes:
            In this parameter table the DRAG pulse type parameter set is assumed.
        """
        name_map = {
            'duration': default_duration,
            'amp': default_amp,
            'phase': default_phase,
            'sigma': default_sigma,
            'beta': default_beta
        }

        fake_table = defaultdict(list)
        for qind in range(n_qubits):
            for gate in FakeSingleQubitTable.GATE_TYPES:
                for pname, default_val in name_map.items():
                    if pname == 'amp' and gate == 'xp':
                        value = default_val * 2
                    else:
                        value = default_val

                    fake_table['qubits'].append((qind, ))
                    fake_table['channel'].append('d{qind:d}'.format(qind=qind))
                    fake_table['inst_name'].append(gate)
                    fake_table['name'].append(pname)
                    fake_table['value'].append(value)
                    fake_table['validation'].append('none')
                    fake_table['timestamp'].append(pd.Timestamp(caldate))

        super().__init__(params_collection=pd.DataFrame(data=fake_table))
