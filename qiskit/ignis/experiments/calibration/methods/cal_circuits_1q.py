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
from qiskit.ignis.experiments.calibration import cal_table, cal_builder, types
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.ignis.experiments.calibration.types import SingleQubitAtomicPulses as Insts


def rabi(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        meas_basis: Optional[str] = 'z') -> types.CalProg:
    """Generate Rabi circuit."""
    if len(target_qubits) != 1:
        raise CalExpError(
            'Invalid number of qubits = {} is specified.'
            'This experiment requires 1 qubit.'.format(len(target_qubits)))

    with cal_builder.build(name=name,
                           qubits=target_qubits,
                           table=table,
                           meas_basis=meas_basis) as circ:
        cal_builder.atomic_gate(name=Insts.STIM.value, qubits=target_qubits)

    meta = {
        'generator': 'rabi',
        'meas_basis': meas_basis
    }

    return types.CalProg(circuits=[circ], metadata=[meta])


def ramsey_xy(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        meas_basis: Optional[str] = 'z') -> types.CalProg:
    """Generate Ramsey circuit."""
    if len(target_qubits) != 1:
        raise CalExpError(
            'Invalid number of qubits = {} is specified.'
            'This experiment requires 1 qubit.'.format(len(target_qubits)))

    delay_param = circuit.Parameter('delay')

    with cal_builder.build(name=name,
                           qubits=target_qubits,
                           table=table,
                           meas_basis=meas_basis) as circ_x:
        cal_builder.atomic_gate(name=Insts.X90P.value, qubits=target_qubits)
        circ_x.delay(delay_param, unit='ns', qarg=[0])
        cal_builder.atomic_gate(name=Insts.X90P.value, qubits=target_qubits)

    with cal_builder.build(name=name,
                           qubits=target_qubits,
                           table=table,
                           meas_basis=meas_basis) as circ_y:
        cal_builder.atomic_gate(name=Insts.X90P.value, qubits=target_qubits)
        circ_y.delay(delay_param, unit='ns', qarg=[0])
        cal_builder.atomic_gate(name=Insts.Y90P.value, qubits=target_qubits)

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

    return types.CalProg(
        circuits=[circ_x, circ_y],
        metadata=[meta_x, meta_y]
    )


def amp_error_amplification(
        name: str,
        table: cal_table.CalibrationDataTable,
        target_qubits: List[int],
        n_reps: List[int],
        meas_basis: Optional[str] = 'z') -> types.CalProg:
    """Generate ping-pong circuit."""
    if len(target_qubits) != 1:
        raise CalExpError(
            'Invalid number of qubits = {} is specified.'
            'This experiment requires 1 qubit.'.format(len(target_qubits)))

    cal_circs = []
    for n_rep in n_reps:
        with cal_builder.build(name=name,
                               qubits=target_qubits,
                               table=table,
                               meas_basis=meas_basis) as circ:
            cal_builder.atomic_gate(name=Insts.X90P.value, qubits=target_qubits)
            # repeat pi pulses
            for _ in range(n_rep):
                cal_builder.atomic_gate(name=Insts.XP.value, qubits=target_qubits)
        cal_circs.append(circ)

    metadata = []
    for n_rep in n_reps:
        meta = {
            'generator': 'amp_error_amplification',
            'meas_basis': meas_basis,
            'rep': n_rep
        }
        metadata.append(meta)

    return types.CalProg(circuits=cal_circs, metadata=metadata)
