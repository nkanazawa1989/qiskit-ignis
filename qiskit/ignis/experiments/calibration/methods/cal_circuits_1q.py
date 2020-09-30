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

from typing import Optional, List

from qiskit import circuit
from qiskit.ignis.experiments.calibration import cal_table, types
from qiskit.ignis.experiments.calibration.cal_base import CalibrationCircuit as Calib


def rabi(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        meas_basis: Optional[str] = 'z') -> types.Program:
    """Generate Rabi circuit."""
    with Calib(name=name, n_qubits=1, meas_basis=meas_basis) as circ:
        circ.append(table.get_gate(
            instruction=types.SingleQubitAtomicPulses.STIM.value,
            qubits=target_qubits
        ), [0])

    meta = {
        'generator': 'rabi',
        'meas_basis': meas_basis
    }

    return [circ], [meta]


def ramsey_xy(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        meas_basis: Optional[str] = 'z') -> types.Program:
    """Generate Ramsey circuit."""
    with Calib(name=name, n_qubits=1, meas_basis=meas_basis) as circ_x:
        circ_x.append(table.get_gate(
            instruction=types.SingleQubitAtomicPulses.X90P.value,
            qubits=target_qubits
        ), [0])
        circ_x.delay(circuit.Parameter('delay'), unit='ns', qarg=[0])
        circ_x.append(table.get_gate(
            instruction=types.SingleQubitAtomicPulses.X90P.value,
            qubits=target_qubits
        ), [0])

    with Calib(name=name, n_qubits=1, meas_basis=meas_basis) as circ_y:
        circ_y.append(table.get_gate(
            instruction=types.SingleQubitAtomicPulses.X90P.value,
            qubits=target_qubits
        ), [0])
        circ_y.delay(circuit.Parameter('delay'), unit='ns', qarg=[0])
        circ_y.append(table.get_gate(
            instruction=types.SingleQubitAtomicPulses.Y90P.value,
            qubits=target_qubits
        ), [0])

        meta_x = {
            'generator': 'ramsey',
            'meas_basis': meas_basis,
            'quad': 'x'
        }
        meta_y = {
            'generator': 'ramsey',
            'meas_basis': meas_basis,
            'quad': 'y'
        }

    return [circ_x, circ_y], [meta_x, meta_y]


def amp_error_amplification(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        n_reps: List[int],
        meas_basis: Optional[str] = 'z') -> types.Program:
    """Generate ping-pong circuit."""
    cal_circs = []
    for n_rep in n_reps:
        with Calib(name=name, n_qubits=1, meas_basis=meas_basis) as circ:
            circ.append(table.get_gate(
                instruction=types.SingleQubitAtomicPulses.X90P.value,
                qubits=target_qubits
            ), [0])
            for _ in range(n_rep):
                circ.append(table.get_gate(
                    instruction=types.SingleQubitAtomicPulses.XP.value,
                    qubits=target_qubits
                ), [0])
        cal_circs.append(circ)

    metadata = []
    for n_rep in n_reps:
        meta = {
            'generator': 'amp_error_amplification',
            'meas_basis': meas_basis,
            'rep': n_rep
        }
        metadata.append(meta)

    return cal_circs, metadata
