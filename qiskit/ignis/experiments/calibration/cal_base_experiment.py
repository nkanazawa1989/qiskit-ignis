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
from typing import List, Dict

from qiskit import transpile, schedule, assemble, pulse, QuantumCircuit
from qiskit.circuit.measure import Measure
from qiskit.providers import BaseBackend, BaseJob

from qiskit.ignis.experiments.base import Experiment


class BaseCalibrationExperiment(Experiment):
    """
    Class for a calibration experiments.
    """

    def schedules(self, backend: BaseBackend) -> List[pulse.Schedule]:
        """Return pulse schedules to submit."""

        # TODO: Add transpiler & scheduler options

        # Get schedule
        circuits = transpile(self.generator.circuits(), backend=backend)

        return schedule(circuits, backend=backend)

    def register_maps(self, backend: BaseBackend) -> List[Dict[int, int]]:
        """Return index mapping of qubits and clbits in measurement instructions."""
        # Get schedule
        circuits = transpile(self.generator.circuits(), backend=backend)

        # Get register index mapping
        regmaps = []
        for circ in circuits:
            regmap = BaseCalibrationExperiment._get_qubit_clbit_map(circ)
            regmaps.append(regmap)

        return regmaps

    def execute(self, backend: BaseBackend, **kwargs) -> 'BaseCalibrationExperiment':
        """Execute the experiment on a backend.
​
        Args:
            backend: backend to run experiment on.
            kwargs: kwargs for assemble method.
​
        Returns:
            BaseJob: the experiment job.
        """

        # Get circuits and metadata
        exp_id = str(uuid.uuid4())

        schedules = self.schedules(backend=backend)
        regmaps = self.register_maps(backend=backend)
        metadata = self.generator.metadata()

        for meta, regmap in zip(metadata, regmaps):
            meta['name'] = self.generator.name
            meta['exp_id'] = exp_id
            meta['qubits'] = self.generator.qubits
            meta['register_map'] = regmap

        # The analysis data processing requires certain predefined data types.
        self.analysis.data_processing_steps.shots = kwargs.get('shots', 1024)
        shots = self.analysis.data_processing_steps.shots

        # Assemble and submit to backend
        qobj = assemble(schedules,
                        backend=backend,
                        qobj_header={'metadata': metadata},
                        meas_level=self.analysis.data_processing_steps.meas_level(),
                        meas_return=self.analysis.data_processing_steps.meas_return(),
                        shots=shots,
                        **kwargs)
        self._job = backend.run(qobj)
        return self

    @classmethod
    def _get_qubit_clbit_map(cls, circ: QuantumCircuit) -> Dict[int, int]:
        """A helper method to get qubit and clbit mapping from the circuit.

        Args:
            circ: QuantuCircuit to investigate.
        """
        register_map = dict()
        for inst, qubits, clbits in circ.data:
            if isinstance(inst, Measure):
                # this mapping doesn't support multiple measurement
                # if there is multiple measurement for a qubit, old index will be overwritten.
                register_map[qubits[0].index] = clbits[0].index

        return register_map
