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

from qiskit import pulse
from qiskit.ignis.experiments.calibration import cal_table, types


class FakeDatabase:
    """Fake calibration database."""

    def __init__(self, num_qubits: int):
        """Create new database."""
        self._table = cal_table.CalibrationDataTable()
        self._num_qubits = num_qubits

        # create single qubit gates
        for qind in range(num_qubits):
            for name in [e.value for e in types.SingleQubitAtomicPulses]:
                gate = cal_table.AtomicGate(
                    name=name,
                    qubits=[qind],
                    channel=pulse.DriveChannel(qind),
                    generator=pulse.Drag,
                    param_names=['duration', 'amp', 'sigma', 'beta'],
                    param_vals=[160, 0, 40, 0]
                )
                self._table.add(
                    instruction=name,
                    qubits=[qind],
                    gate=gate
                )

    def load_calibrations(self) -> cal_table.CalibrationDataTable:
        """Acquire calibration table."""
        return self._table

    def update_calibrations(self, table: cal_table.CalibrationDataTable):
        """Update calibration table."""
        self._table._map.update(table._map)
