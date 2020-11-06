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
from typing import List

from qiskit import transpile, schedule, assemble, pulse
from qiskit.providers import BaseBackend, BaseJob

from qiskit.ignis.experiments.base import Experiment


class BaseCalibrationExperiment(Experiment):
    """
    Class for a calibration experiments.
    Typically we calibrate pulse parameters. These pulse parameters are
    stored in a table with their values. The calibration experiments
    rely on generators to produce the circuits and analyze the data
    with an Analysis class, typically responsible for extracting pulse
    parameters from the data. The analysis defines the steps by which
    the data is processed.
    """

    def schedules(self, backend: BaseBackend) -> List[pulse.Schedule]:
        """Return pulse schedules to submit."""

        # TODO: Add transpiler & scheduler options

        # check backend consistency
        #if backend.name() != self.generator.associated_backend:
        #    raise CalExpError('Executing on the wrong backend. '
        #                      'Pulse are generated based on the calibration table of {back1}, '
        #                      'but experiments are running on {back2}.'
        #                      ''.format(back1=self.generator.table.backend_name,
        #                                back2=backend.name()))

        # Get schedule
        circuits = transpile(self.generator.circuits(),
                             backend=backend,
                             initial_layout=self.generator.qubits)
        return schedule(circuits, backend=backend)

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
        metadata = self.generator.metadata()

        for meta in metadata:
            meta['name'] = self.generator.name
            meta['exp_id'] = exp_id
            meta['qubits'] = self.generator.qubits

        # The analysis data processing requires certain predefined data types.
        self.analysis.workflow.shots = kwargs.get('shots', 1024)
        shots = self.analysis.workflow.shots
        meas_level = self.analysis.workflow.meas_level()
        meas_return = self.analysis.workflow.meas_return()

        # Assemble and submit to backend
        qobj = assemble(schedules,
                        backend=backend,
                        qobj_header={'metadata': metadata},
                        meas_level=meas_level,
                        meas_return=meas_return,
                        shots=shots,
                        **kwargs)
        self._job = backend.run(qobj)
        return self
