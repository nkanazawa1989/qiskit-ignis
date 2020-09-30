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

"""Single qubit gate calibration."""

from typing import Optional, Dict, List

from qiskit import QuantumCircuit, circuit
from qiskit.ignis.experiments.calibration import cal_base, types


class Rabi(cal_base.CalSubsetGenerator):
    """Generate Rabi circuit."""
    N_CAL_QUBITS = 1

    def circuits(self) -> List[QuantumCircuit]:
        """Generate experimental circuits."""
        with cal_base.CalibrationCircuit(
                name=self.name,
                n_qubits=self.N_CAL_QUBITS,
                meas_basis=self._meas_basis) as cal_circ:
            cal_circ.append(self._parent.cal_table.get_gate(
                instruction=types.SingleQubitAtomicPulses.STIM,
                qubits=self.qubits
            ), [0])

        return [cal_circ]

    def _extra_metadata(self) -> List[Dict[str, any]]:
        """Generate a list of experiment metadata dicts."""
        metadata = {
            'generator': self.__class__.__name__,
            'meas_basis': self._meas_basis
        }

        return [metadata]


class RamseyXY(cal_base.CalSubsetGenerator):
    """Generate RamseyXY circuit."""
    N_CAL_QUBITS = 1

    def circuits(self) -> List[QuantumCircuit]:
        """Generate experimental circuits."""
        with cal_base.CalibrationCircuit(
                name=self.name,
                n_qubits=self.N_CAL_QUBITS,
                meas_basis=self._meas_basis) as cal_circ_x:
            cal_circ_x.append(self._parent.cal_table.get_gate(
                instruction=types.SingleQubitAtomicPulses.X90P,
                qubits=self.qubits
            ), [0])
            cal_circ_x.delay(circuit.Parameter('delay'), unit='ns', qarg=self.qubits)
            cal_circ_x.append(self._parent.cal_table.get_gate(
                instruction=types.SingleQubitAtomicPulses.X90P,
                qubits=self.qubits
            ), [0])

        with cal_base.CalibrationCircuit(
                name=self.name,
                n_qubits=self.N_CAL_QUBITS,
                meas_basis=self._meas_basis) as cal_circ_y:
            cal_circ_y.append(self._parent.cal_table.get_gate(
                instruction=types.SingleQubitAtomicPulses.X90P,
                qubits=self.qubits
            ), [0])
            cal_circ_y.delay(circuit.Parameter('delay'), unit='ns', qarg=self.qubits)
            cal_circ_y.append(self._parent.cal_table.get_gate(
                instruction=types.SingleQubitAtomicPulses.Y90P,
                qubits=self.qubits
            ), [0])

        return [cal_circ_x, cal_circ_y]

    def _extra_metadata(self) -> List[Dict[str, any]]:
        """Generate a list of experiment metadata dicts."""
        metadata_x = {
            'generator': self.__class__.__name__,
            'meas_basis': self._meas_basis,
            'quad': 'x'
        }
        metadata_y = {
            'generator': self.__class__.__name__,
            'meas_basis': self._meas_basis,
            'quad': 'y'
        }

        return [metadata_x, metadata_y]


class AmpErrorAmplification(cal_base.CalSubsetGenerator):
    """Generate RamseyXY circuit."""
    N_CAL_QUBITS = 1

    def __init__(self,
                 parent: cal_base.PulseGenerator,
                 n_reps: List[int],
                 meas_basis: Optional[str] = None):
        """Initialize generator."""
        self._n_reps = n_reps

        super().__init__(parent=parent, meas_basis=meas_basis)

    def circuits(self) -> List[QuantumCircuit]:
        """Generate experimental circuits."""
        cal_circs = []
        for n_rep in self._n_reps:
            with cal_base.CalibrationCircuit(
                    name=self.name,
                    n_qubits=self.N_CAL_QUBITS,
                    meas_basis=self._meas_basis) as cal_circ:
                cal_circ.append(self._parent.cal_table.get_gate(
                    instruction=types.SingleQubitAtomicPulses.X90P,
                    qubits=self.qubits
                ), [0])
                for _ in range(n_rep):
                    cal_circ.append(self._parent.cal_table.get_gate(
                        instruction=types.SingleQubitAtomicPulses.XP,
                        qubits=self.qubits
                    ), [0])
            cal_circs.append(cal_circ)

        return cal_circs

    def _extra_metadata(self) -> List[Dict[str, any]]:
        """Generate a list of experiment metadata dicts."""
        metadata = []
        for n_rep in self._n_reps:
            meta = {
                'generator': self.__class__.__name__,
                'meas_basis': self._meas_basis,
                'rep': n_rep
            }
            metadata.append(meta)

        return metadata
