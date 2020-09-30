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

"""Qiskit Ignis calibration module."""

from copy import deepcopy
from typing import Union, List, Optional, Dict, Iterable, Any

from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.ignis.experiments.base import Generator, Experiment, Analysis
from qiskit.ignis.experiments.calibration.cal_table import CalibrationDataTable
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from collections import defaultdict


class CalibrationExperiment(Experiment):

    def __init__(self,
                 cal_table: CalibrationDataTable,

                 generator: Optional[Generator] = None,
                 analysis: Optional[Analysis] = None,
                 job: Optional = None):






class PulseGenerator(Generator):
    """A generator class for a schedule based circuits."""
    def __init__(self,
                 cal_name: str,
                 num_qubits: int,
                 cal_generator: Generator,
                 cal_table: CalibrationDataTable):
        """Create new high level generator for calibration.

        Args:
            cal_name: Name of this calibration.
            num_qubits: Number of qubits in the target quantum processor.
            cal_generator: Generator of calibration circuit.
            cal_table: Table of calibration data.
        """
        self._cal_table = cal_table
        self._cal_generator = cal_generator

        self._circuits = []
        self._metadata = []

        # parameter scans
        self._defined_parameters = set()
        self._assigned_circuits = []
        self._assigned_metadata = []

        super().__init__(name=cal_name, qubits=num_qubits)

        # reset qubit
        self.qubits = []

    @property
    def cal_table(self) -> CalibrationDataTable:
        """Return calibration data table."""
        return self._cal_table

    @property
    def qubits(self) -> List[int]:
        """Return the qubits for this experiment."""
        return self._qubits

    @qubits.setter
    def qubits(self, value: Iterable[int]):
        """Set the qubits for this experiment. Note that this is physical qubit."""
        self._qubits = list(value)

    def _bind_calibration(self, circ: QuantumCircuit) -> QuantumCircuit:
        """Bind calibration to circuit.

        Note:
            Calibration circuit is agnostic to actual qubit until this method is called.
        """

        # TODO:
        #  replace u1, u2, u3 and cx with generated schedules from cal_table.
        #  this requires synchronization of channel frames thus compiler is required.

        # add calibrations for custom pulse gate
        for inst, qubits, clbits in circ.data:
            inst_name = inst.name
            qinds = [qubit.index for qubit in qubits]

            if self._cal_table.has(inst_name, qinds):
                # add new calibration entry if the key is found in the calibration table
                circ.add_calibration(
                    gate=inst_name,
                    qubits=qinds,
                    schedule=self._cal_table.get_schedule(inst_name, qinds),
                    params=self._cal_table.get_parameters(inst_name, qinds)
                )

        return circ

    def add_experiment(self, qubits: Union[int, List[int]]):
        """Generate calibration experiment for specified subset of qubits.

        Args:
            qubits: List of target qubit subset for this calibration.
        """

        # TODO:
        #  allow this to create simultaneous calibration for multiple subset qubits
        #  by calling this multiple times with different qubits kwarg.

        if isinstance(qubits, int):
            qubits = [qubits]

        self._cal_generator.qubits = qubits

        for temp_circ in self._cal_generator.circuits():
            # store parameters in generated circuits
            self._defined_parameters.update(temp_circ.parameters)

            # generate physical circuit
            circ = QuantumCircuit(self.num_qubits, self.num_qubits)
            circ.compose(temp_circ, qubits=qubits, inplace=True)
            self._circuits.append(self._bind_calibration(circ))

        self._metadata.extend(self._cal_generator.metadata())

        # validation
        if len(self._circuits) != len(self._metadata):
            raise CalExpError('Number of circuits and metadata are not identical.'
                              '{}!={}'.format(len(self._circuits), len(self._metadata)))

        # add this qubit subset
        self.qubits = set(self.qubits + qubits)

    def assign_parameters(self,
                          parameters: Dict[Union[str, Parameter], Iterable[Union[int, float]]]):
        """Assign values to scan for parameters.

        If length of bind values are different, scan is limited to the parameter
        with the shortest length.
        """
        self._assigned_circuits.clear()
        self._assigned_metadata.clear()

        # convert keys to string. parameter names in calibration should be unique.
        str_parameters = {}
        for param, values in parameters:
            if isinstance(param, str):
                str_parameters[param] = values
            else:
                str_parameters[param.name] = values

        for circ, meta in zip(self._circuits, self._metadata):
            active_params = [param for param in circ.parameters if param.name in str_parameters]
            # nothing to bind
            if not active_params:
                self._assigned_circuits.append(circ)
                self._assigned_metadata.append(meta)
                continue

            # generate parameter bind
            active_scans = [str_parameters[param.name] for param in active_params]
            for scan_vals in zip(*active_scans):
                bind_dict = dict(zip(active_params, scan_vals))
                temp_meta = deepcopy(meta)
                temp_meta.update(bind_dict)
                self._assigned_circuits.append(circ.assign_parameters(bind_dict, inplace=False))
                self._assigned_metadata.append(temp_meta)

    def circuits(self) -> List[QuantumCircuit]:
        """Generate a list of experiment circuits."""
        return self._assigned_circuits

    def _extra_metadata(self) -> List[Dict[str, Any]]:
        """Generate a list of experiment circuits metadata."""
        return self._assigned_metadata


class CalSubsetGenerator(Generator):
    """Generator of calibration subset."""
    N_CAL_QUBITS = 1

    def __init__(self,
                 parent: PulseGenerator,
                 meas_basis: Optional[List[str]] = None):
        """Initialize generator."""
        self._parent = parent
        self._meas_basis = meas_basis

        super().__init__(name=self._parent.name, qubits=self.N_CAL_QUBITS)

    def circuits(self) -> List[QuantumCircuit]:
        """Return a list of experiment circuits."""
        raise NotImplementedError

    def _extra_metadata(self) -> List[Dict[str, any]]:
        """Generate a list of experiment metadata dicts."""
        raise NotImplementedError


class CalibrationCircuit:
    def __init__(self,
                 name: str,
                 n_qubits: int,
                 meas_basis: Optional[List[str]] = None):

        if isinstance(meas_basis, str):
            meas_basis = [meas_basis]

        self._circuit = QuantumCircuit(n_qubits, n_qubits, name=name)
        self._meas_basis = meas_basis or ['z'] * n_qubits

        # validation
        if len(self._meas_basis) != n_qubits:
            raise CalExpError('Number of measurement basis is not '
                              'identical to the number of qubits.')

    def __enter__(self):
        """Add calibration and LO initialization sequence at the beginning of circuit.

        Implicitly assume the mapping of qubit and channel with the same index.
        """

        # TODO:
        #  set frequency gate is required to ensure constant LO frequency during experiment.
        #  this info should be globally defined for each channel,
        #  thus different data model is required.

        return self._circuit

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Insert measurement in specified measurement basis and add calibration."""
        from qiskit.converters.circuit_to_dag import circuit_to_dag

        # add measurement to active qubits with arbitrary Pauli basis
        dag = circuit_to_dag(self._circuit)
        active_qubits = [qubit for qubit in self._circuit.qubits if qubit not in dag.idle_wires()]
        self._circuit.barrier(*active_qubits)
        for qubit in active_qubits:
            if self._meas_basis[qubit.index] == 'Y':
                self._circuit.sdg(qubit)
            if self._meas_basis[qubit.index] in ['X', 'Y']:
                self._circuit.h(qubit)
            self._circuit.measure(qubit.index, qubit.index)

        return None
