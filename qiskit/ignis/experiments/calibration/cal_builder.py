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

"""Qiskit Ignis calibration builder."""

import contextvars
from typing import Optional, List, Union, ContextManager

from qiskit import QuantumCircuit
from qiskit.ignis.experiments.calibration import cal_table
from qiskit.ignis.experiments.calibration.exceptions import CalExpError

#: contextvars.ContextVar[BuilderContext]: active builder
BUILDER_CONTEXTVAR = contextvars.ContextVar("backend")


class _CalibrationBuilder:
    """Builder context class."""

    def __init__(self,
                 name: str,
                 qubits: List[int],
                 table: cal_table.CalibrationDataTable,
                 meas_basis: Optional[List[str]] = None):
        """Calibration circuit cuilder.

        Args:
           name: Name of this calibration. This name is applied to generated circuit.
           qubits: Index of physical qubits to calibrate.
           table: Mapping of gate name to atomic gate.
           meas_basis: Basis of measurement.
        """
        if isinstance(meas_basis, str):
            meas_basis = [meas_basis]

        self._qubits = qubits
        self._table = table

        #: Union[None, ContextVar]: Token for this ``_CalibrationBuilder``'s ``ContextVar``.
        self._backend_ctx_token = None

        n_qubits = len(qubits)
        self._circuit = QuantumCircuit(n_qubits, n_qubits, name=name)
        self._meas_basis = meas_basis or ['z'] * n_qubits

        # validation
        if len(self._meas_basis) != n_qubits:
            raise CalExpError(
                'Number of measurement basis is not '
                'identical to the number of qubits.')

    def __enter__(self):
        """Add calibration and LO initialization sequence at the beginning of circuit.

        Implicitly assume the mapping of qubit and channel with the same index.
        """

        # TODO:
        #  set frequency gate is required to ensure constant LO frequency during experiment.
        #  this info should be globally defined for each channel,
        #  thus different data model is required.

        self._backend_ctx_token = BUILDER_CONTEXTVAR.set(self)
        return self._circuit

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Insert measurement in specified measurement basis and add calibration."""
        # convert logical index to physical index
        self._circuit.barrier()
        for qind, basis in enumerate(self._meas_basis):
            if basis == 'Y':
                self._circuit.sdg(qind)
            if basis in ['X', 'Y']:
                self._circuit.h(qind)
            self._circuit.measure(qind, qind)

        # add calibration to circuit
        for inst, qubits, _ in self._circuit.data:
            inst_name = inst.name

            # convert logical index to physical index
            qinds = [self._qubits[qubit.index] for qubit in qubits]

            if self._table.has(inst_name, qinds):
                # add new calibration entry if the key is found in the calibration table
                self._circuit.add_calibration(
                    gate=inst_name,
                    qubits=qinds,
                    schedule=self._table.get_schedule(inst_name, qinds),
                    params=self._table.get_parameters(inst_name, qinds)
                )
        BUILDER_CONTEXTVAR.reset(self._backend_ctx_token)

    def append_atomic(self,
                      name: str,
                      qubits: List[int]):
        """Append gate instruction from calibration table.

        Args:
            name: Name of atomic instruction.
            qubits: Index of physical qubit.
        """
        atomic_gate = self._table.get_gate(instruction=name, qubits=qubits)
        logical_qinds = [self._qubits.index(qind) for qind in qubits]

        self._circuit.append(atomic_gate, logical_qinds)


def build(name: str,
          qubits: List[int],
          table: cal_table.CalibrationDataTable,
          meas_basis: Optional[List[str]] = None
          ) -> ContextManager[QuantumCircuit]:
    """Create a context manager for launching the imperative calibration builder DSL"""

    return _CalibrationBuilder(
        name=name,
        qubits=qubits,
        table=table,
        meas_basis=meas_basis
    )


def _active_builder() -> _CalibrationBuilder:
    """Get the active builder in the active context."""
    try:
        return BUILDER_CONTEXTVAR.get()
    except LookupError:
        raise CalExpError(
            'A calibration builder function was called outside of '
            'a builder context. Try calling within a builder '
            'context, eg., "with calibration.build() as circ: ...".')


def atomic_gate(
        name: str,
        qubits: Union[int, List[int]]):
    """Add atomic gate to circuit.

    Args:
        name: Name of atomic instruction.
        qubits: Index of target qubits.
    """
    if isinstance(qubits, int):
        qubits = [qubits]

    _active_builder().append_atomic(name=name, qubits=qubits)
