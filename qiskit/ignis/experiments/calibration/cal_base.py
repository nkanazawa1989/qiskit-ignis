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

import uuid
from copy import deepcopy
from typing import Union, List, Optional, Dict, Iterable, Callable

from qiskit import QuantumCircuit, transpile, schedule, assemble
from qiskit.circuit import Parameter
from qiskit.ignis.experiments.base import Generator, Experiment
from qiskit.ignis.experiments.calibration.cal_table import CalibrationDataTable
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.providers import BaseBackend
from qiskit.providers import BaseJob


class BaseCalibrationExperiment(Experiment):
    """An experiment class for a calibration experiment."""

    def execute(self, backend: BaseBackend, **kwargs) -> BaseJob:
        """Execute the experiment on a backend.
​
        TODO: Add transpiler & scheduler options

        Args:
            backend: backend to run experiment on.
            kwargs: kwargs for assemble method.
​
        Returns:
            BaseJob: the experiment job.
        """
        # check backend consistency
        if backend.name() != self.generator.table.backend_name:
            raise CalExpError('Executing on the wrong backend. '
                              'Pulse are generated based on the calibration table of {back1}, '
                              'but experiments are running on {back2}.'
                              ''.format(back1=self.generator.table.backend_name,
                                        back2=backend.name()))

        # Get circuits and metadata
        exp_id = str(uuid.uuid4())
        circuits = transpile(self.generator.circuits(),
                             backend=backend,
                             initial_layout=self.generator.qubits)
        scheds = schedule(circuits, backend=backend)
        metadata = self.generator.metadata()

        for meta in metadata:
            meta['name'] = self.generator.name
            meta['exp_id'] = exp_id
            meta['qubits'] = self.generator.qubits

        return scheds, metadata

        # # Assemble qobj and submit to backend
        # qobj = assemble(scheds,
        #                 backend=backend,
        #                 qobj_header={'metadata': metadata},
        #                 **kwargs)
        # self._job = backend.run(qobj)
        # return self


class BaseCalibrationGenerator(Generator):
    """A generator class for calibration circuit generation.

    # TODO support simultaneous calibration
    """
    def __init__(self,
                 cal_name: str,
                 target_qubits: Union[int, List[int]],
                 cal_generator: Callable,
                 table: CalibrationDataTable,
                 **kwargs):
        """Create new high level generator for calibration.

        Args:
            cal_name: Name of this calibration.
            target_qubits: Target qubit of this calibration.
            cal_generator: Generator of calibration circuit.
            table: Table of calibration data.
        """
        try:
            self.target_qubits = list(target_qubits)
        except TypeError:
            self.target_qubits = [target_qubits]

        super().__init__(name=cal_name, qubits=target_qubits)
        self._table = table

        self._defined_parameters = set()
        self._circuits = []
        self._metadata = []

        cal_prog = cal_generator(
            name=self.name,
            table=self._table,
            target_qubits=target_qubits,
            **kwargs
        )

        # store parameters in generated circuits
        for temp_circ in cal_prog.circuits:
            self._defined_parameters.update(temp_circ.parameters)

        # validation
        if len(cal_prog.circuits) != len(cal_prog.metadata):
            raise CalExpError(
                'Number of circuits and metadata are not identical.'
                '{}!={}'.format(len(cal_prog.circuits), len(cal_prog.metadata)))

        self._unassigned_circuits = cal_prog.circuits
        self._unassigned_metadata = cal_prog.metadata

    @property
    def table(self):
        """Return calibration table."""
        return self._table

    # def _bind_calibration(self, circ: QuantumCircuit) -> QuantumCircuit:
    #     """Bind calibration to circuit.
    #
    #     Note:
    #         Calibration circuit is agnostic to actual qubit until this method is called.
    #     """
    #
    #     # TODO:
    #     #  replace u1, u2, u3 and cx with generated schedules from cal_table.
    #     #  this requires synchronization of channel frames thus compiler is required.
    #
    #     # add calibrations for custom pulse gate
    #     for inst, qubits, clbits in circ.data:
    #         inst_name = inst.name
    #
    #         # qinds should be physical qubit index, otherwise transpiler cannot find entry.
    #         qinds = [self.target_qubits[qubit.index] for qubit in qubits]
    #
    #         if self._table.has(inst_name, qinds):
    #             # add new calibration entry if the key is found in the calibration table
    #             circ.add_calibration(
    #                 gate=inst_name,
    #                 qubits=qinds,
    #                 schedule=self._table.get_schedule(inst_name, qinds),
    #                 params=self._table.get_parameters(inst_name, qinds)
    #             )
    #
    #     return circ

    def assign_parameters(self,
                          parameters: Dict[Union[str, Parameter], Iterable[Union[int, float]]]):
        """Assign values to scan for parameters.

        If length of bind values are different, scan is limited to the parameter
        with the shortest length.
        """
        self._circuits.clear()
        self._metadata.clear()

        # convert keys to string. parameter names in calibration should be unique.
        str_parameters = {}
        for param, values in parameters.items():
            if isinstance(param, str):
                str_parameters[param] = values
            else:
                str_parameters[param.name] = values

        for circ, meta in zip(self._unassigned_circuits, self._unassigned_metadata):
            active_params = [param for param in circ.parameters if param.name in str_parameters]

            # nothing to bind
            if not active_params:
                self._circuits.append(circ)
                self._metadata.append(meta)
                continue

            # generate parameter bind
            active_scans = [str_parameters[param.name] for param in active_params]
            for scan_vals in zip(*active_scans):
                bind_dict = dict(zip(active_params, scan_vals))
                temp_meta = deepcopy(meta)
                temp_meta.update({param.name: val for param, val in bind_dict.items()})
                self._circuits.append(circ.assign_parameters(bind_dict, inplace=False))
                self._metadata.append(temp_meta)

    def circuits(self) -> List[QuantumCircuit]:
        """Return a list of experiment circuits."""
        return self._circuits

    def _extra_metadata(self) -> List[Dict[str, any]]:
        """Generate a list of experiment metadata dicts."""
        return self._metadata
