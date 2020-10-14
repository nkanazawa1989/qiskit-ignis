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
from typing import Union, Dict, List, Callable, Iterable, Optional, Any

from qiskit import QuantumCircuit, transpile, schedule, assemble, pulse
from qiskit.circuit import Parameter
from qiskit.ignis.experiments.base import Generator, Experiment, Analysis
from qiskit.ignis.experiments.calibration.cal_table import CalibrationDataTable
from qiskit.ignis.experiments.calibration.workflow import AnalysisWorkFlow
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.providers import BaseBackend, BaseJob
from qiskit.result import Result, Counts, utils as res_util


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

        # calibration generator is not agnostic to backend because
        # pulse schedule is specific to each physical qubit.
        # this value is used to validation of backend consistency when submitting job.
        self.associated_backend = table.backend_name

        super().__init__(name=cal_name, qubits=target_qubits)

        self._defined_parameters = set()
        self._circuits = []
        self._metadata = []

        cal_prog = cal_generator(
            name=self.name,
            table=table,
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


class BaseCalibrationAnalysis(Analysis):
    """Calibration experiment analysis."""

    def __init__(self,
                 qubits: List[int],
                 name: Optional[str] = None,
                 data: Optional[Any] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 exp_id: Optional[str] = None):
        """Initialize calibration experiment analysis

        Args:
            qubits: Index of qubits to analyze.
            name: Name of this analysis.
            data: Result data to initialize with.
            metadata: Metadata to initialize with.
            exp_id: Experiment id string.

        Additional Information:
            Pulse job doesn't return marginalized result.
            If Result object is provided it is marginalized based on specified qubit.
            Direct index mapping between qubit and classical bit is assumed.

            User don't need to take care of data format.
            Proper fitter is selected based on the data format.
        """
        self.qubits = qubits

        super().__init__(data=data,
                         metadata=metadata,
                         name=name,
                         exp_id=exp_id)

    def _format_data(self,
                     data: Result,
                     metadata: Dict[str, any],
                     index: int) -> Counts:
        """Format the required data from a Result.data dict"""

        result = data.results[index]

        if result.meas_level == 2:
            res_trunc = res_util.marginal_counts(result=result, indices=self.qubits)
            return res_trunc.get_counts(index)
        elif result.meas_level == 1:
            if result.meas_return == 'single':
                pass
            elif result.meas_return == 'avg':
                pass
            else:
                raise CalExpError(
                    'Experiment result with unsupported measurement '
                    'format {} is provided.'.format(result.meas_return))
        else:
            raise CalExpError(
                'Experiment result with unsupported measurement ' 
                'level {} is provided.'.format(result.meas_level))


class BaseCalibrationExperiment(Experiment):
    """An experiment class for a calibration experiment."""
    def __init__(self,
                 generator: Optional[BaseCalibrationGenerator] = None,
                 analysis: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional[BaseJob] = None,
                 workflow: Optional[AnalysisWorkFlow] = None):
        """Initialize an experiment."""
        self._workflow = workflow
        super().__init__(generator=generator,
                         analysis=analysis,
                         job=job)

    @property
    def workflow(self):
        """Return workflow for measurement data processing."""
        return self._workflow

    @workflow.setter
    def workflow(self, workflow: AnalysisWorkFlow):
        """Set workflow for measurement data processing."""
        if not isinstance(workflow, AnalysisWorkFlow):
            raise CalExpError('Invalid workflow object.')
        self._workflow = workflow

    def schedules(self, backend: BaseBackend) -> List[pulse.Schedule]:
        """Return pulse schedules to submit."""

        # TODO: Add transpiler & scheduler options

        # check backend consistency
        if backend.name() != self.generator.associated_backend:
            raise CalExpError('Executing on the wrong backend. '
                              'Pulse are generated based on the calibration table of {back1}, '
                              'but experiments are running on {back2}.'
                              ''.format(back1=self.generator.table.backend_name,
                                        back2=backend.name()))

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

        # store shots information for post processing
        self.workflow.shots = kwargs.get('shots', 1024)

        # Assemble qobj and submit to backend
        qobj = assemble(schedules,
                        backend=backend,
                        qobj_header={'metadata': metadata},
                        meas_level=self.workflow.meas_level(),
                        meas_return=self.workflow.meas_return(),
                        shots=self.workflow.shots,
                        **kwargs)
        self._job = backend.run(qobj)
        return self
