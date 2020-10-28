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

"""Data source to generate schedule."""

from typing import Optional, List, Callable, Union, Dict

import numpy as np

from qiskit.ignis.experiments.calibration import (cal_base_experiment,
                                                  cal_base_generator,
                                                  cal_base_fitter,
                                                  cal_table,
                                                  sequences,
                                                  types,
                                                  fitters,
                                                  workflow)
from qiskit.ignis.experiments.base import Generator
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.pulse import DriveChannel, Play, Gaussian, Schedule
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, ParameterExpression, Gate


class RoughSpectroscopy(cal_base_experiment.BaseCalibrationExperiment):

    # pylint: disable=arguments-differ
    def __init__(self,
                 table: cal_table.CalibrationDataTable,
                 qubit: int,
                 data_processing: workflow.AnalysisWorkFlow,
                 freq_vals: np.ndarray,
                 amplitude: float = 0.05,
                 sigma: float = 360,
                 duration: int = 1440,
                 analysis: Optional[cal_base_fitter.BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        entry = types.SingleQubitAtomicPulses.STIM.value

        if not table.has(
            instruction=entry,
            qubits=[qubit]
        ):
            raise CalExpError('Entry {name} does not exist. '
                              'Check your calibration table.'.format(name=entry))

        # setup spectroscopy pulse
        new_params = {'amp': amplitude, 'sigma': sigma, 'duration': duration}

        for key, val in new_params.items():
            table.set_parameter(
                instruction=entry,
                qubits=[qubit],
                param_name=key,
                param_value=val
            )

        # parametrize table
        freq = table.parametrize(
            instruction=entry,
            qubits=[qubit],
            param_name='sideband'
        )

        # setup generator
        generator = cal_base_generator.BaseCalibrationGenerator(
            cal_name='rough_spectroscopy',
            target_qubits=[qubit],
            cal_generator=sequences.rabi,
            table=table,
            meas_basis='z'
        )
        generator.assign_parameters({freq: freq_vals})

        # setup analysis
        if analysis is None:
            analysis = fitters.GaussianFit(
                name='rough_spectroscopy'
            )
        analysis.parameter = freq

        super().__init__(generator=generator,
                         analysis=analysis,
                         job=job,
                         workflow=data_processing)


class RoughAmplitudeCalibration(cal_base_experiment.BaseCalibrationExperiment):

    # pylint: disable=arguments-differ
    def __init__(self,
                 table: cal_table.CalibrationDataTable,
                 qubit: int,
                 data_processing: workflow.AnalysisWorkFlow,
                 amp_vals: np.ndarray,
                 sigma: float = 40,
                 duration: int = 160,
                 analysis: Optional[cal_base_fitter.BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        entry = types.SingleQubitAtomicPulses.STIM.value

        if not table.has(
            instruction=entry,
            qubits=[qubit]
        ):
            raise CalExpError('Entry {name} does not exist. '
                              'Check your calibration table.'.format(name=entry))

        # parametrize table
        amp = table.parametrize(
            instruction=entry,
            qubits=[qubit],
            param_name='amp'
        )

        # setup spectroscopy pulse
        new_params = {'sigma': sigma, 'duration': duration}

        for key, val in new_params.items():
            table.set_parameter(
                instruction=entry,
                qubits=[qubit],
                param_name=key,
                param_value=val
            )

        # setup generator
        generator = cal_base_generator.BaseCalibrationGenerator(
            cal_name='rough_amplitude',
            target_qubits=[qubit],
            cal_generator=sequences.rabi,
            table=table,
            meas_basis='z'
        )

        generator.assign_parameters({amp: amp_vals})

        # setup analysis
        if analysis is None:
            analysis = fitters.CosinusoidalFit(
                name='rough_amplitude'
            )
        analysis.parameter = amp

        super().__init__(generator=generator,
                         analysis=analysis,
                         job=job,
                         workflow=data_processing)


class RabiGenerator(Generator):
    """A Generator for Rabi amplitude scans."""

    def __init__(self,
                 qubits: Union[int, List[int]],
                 parameters: Dict,
                 amplitudes: List,
                 pulse: Callable = None):
        """
        Args:
            qubits: List of qubits to which this calibration can be applied.
            parameters: The arguments for the pulse schedule.
            amplitudes: A list of amplitudes for which to generate a circuit.
            pulse: A parametric pulse function used to generate the schedule
                that is added to the circuits. This defaults to Gaussian and
                parameters should contain 'duration', and 'sigma'.
        """
        super().__init__('Single pulse generator', qubits)
        self._pulse = pulse
        self.parameters = parameters
        self.amplitudes = amplitudes

        # Add the amplitude in the parameters if not supplied.
        if 'amp' not in self.parameters:
            self.parameters['amp'] = Parameter('α')
        elif not isinstance(self.parameters['amp'], ParameterExpression):
            self.parameters['amp'] = Parameter('α')

        # Define the QuantumCircuit that this generator will use.
        self.qc = QuantumCircuit(self._num_qubits, self._num_qubits)
        for qubit in self._qubits:
            gate = Gate('Rabi', 1, [self.parameters['amp']])
            self.qc.append(gate, [qubit])
            self.qc.add_calibration(gate, [qubit], self._schedule(qubit))

        self.qc.measure(self._qubits, self._qubits)

    def circuits(self) -> List[QuantumCircuit]:
        """
        Return a list of experiment circuits.
        This function is also responsible for adding the
        meta data to the circuits.
        """
        return [self.qc.assign_parameters({self.parameters['amp']: amp})
                for amp in self.amplitudes]

    def _schedule(self, qubit: int) -> Schedule:
        """
        Args:
            qubit: The qubit to which this schedule is applied.
        """
        schedule = Schedule(name='Rabi amplitude')
        if self._pulse is None:
            return schedule.insert(0, Play(Gaussian(**self.parameters), DriveChannel(qubit)))
        else:
            return schedule.insert(0, Play(self._pulse(**self.parameters), DriveChannel(qubit)))

    def _extra_metadata(self):
        pass
