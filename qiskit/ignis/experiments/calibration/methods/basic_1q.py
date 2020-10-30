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
from qiskit.pulse import DriveChannel, Play, Gaussian, Schedule, SetFrequency, ShiftPhase
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
        #generator = cal_base_generator.BaseCalibrationGenerator(
        #    cal_name='rough_amplitude',
        #    target_qubits=[qubit],
        #    cal_generator=sequences.rabi,
        #    table=table,
        #    meas_basis='z'
        #)
        generator = SinglePulseSingleParameterGenerator([qubit], new_params, amp_vals, 'amp', 'Rabi')

        #generator.assign_parameters({amp: amp_vals})

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


class SinglePulseSingleParameterGenerator(Generator):
    """
    A generator that generates single pulses and scans a single parameter
    of that pulse. Note that the same pulse may be applied to multiple qubits
    to perform simultaneous calibration.
    """

    def __init__(self,
                 qubits: Union[int, List[int]],
                 parameters: Dict,
                 amplitudes: Union[List, np.array],
                 scanned_parameter: str,
                 name: str,
                 pulse: Callable = None):
        """
        Args:
            qubits: List of qubits to which this calibration can be applied.
            parameters: The arguments for the pulse schedule.
            amplitudes: A list of amplitudes for which to generate a circuit.
            scanned_parameter: Name of the scanned parameter. If it is not present
                in the parameters dictionary as a ParameterExpression it will
                be added to this dict.
            pulse: A parametric pulse function used to generate the schedule
                that is added to the circuits. This defaults to Gaussian and
                parameters should contain 'duration', and 'sigma'.
        """
        super().__init__(name, qubits)
        self._pulse = pulse
        self.parameters = parameters
        self.scanned_values = amplitudes
        self.scanned_parameter = scanned_parameter

        # Add the parameter to be scanned if not supplied.
        if scanned_parameter not in self.parameters:
            self.parameters[scanned_parameter] = Parameter('α')
        elif not isinstance(self.parameters[scanned_parameter], ParameterExpression):
            self.parameters[scanned_parameter] = Parameter('α')

        # Define the QuantumCircuit that this generator will use.
        self.qc = QuantumCircuit(max(self._qubits)+1, max(self._qubits)+1)
        for qubit in self._qubits:
            gate = Gate(scanned_parameter, 1, [self.parameters[scanned_parameter]])
            self.qc.append(gate, [qubit])
            self.qc.add_calibration(gate, [qubit], self._schedule(qubit),
                                    self.parameters[scanned_parameter])

        self.qc.measure(self._qubits, self._qubits)

    def circuits(self) -> List[QuantumCircuit]:
        """
        Return a list of experiment circuits.
        This function is also responsible for adding the
        meta data to the circuits.
        """
        return [self.qc.assign_parameters({self.parameters[self.scanned_parameter]: val})
                for val in self.scanned_values]

    def _schedule(self, qubit: int) -> Schedule:
        """
        Creates the schedules that will be added to the circuit.

        Args:
            qubit: The qubit to which this schedule is applied.
        """
        sched = Schedule(name=self.scanned_parameter)
        ch = DriveChannel(qubit)

        # TODO Some backends apparently don't support SetFrequency and SetPhase
        sched += sched.insert(0, SetFrequency(self.parameters.get('frequency', 0.), ch))
        sched += sched.insert(0, ShiftPhase(self.parameters.get('phase', 0.), ch))

        # Frequency shift and phase shift are not part of a pulse.
        params = {}
        for key, value in self.parameters.items():
            if key not in ['frequency', 'phase']:
                params[key] = value

        if self._pulse is None:
            sched += sched.insert(0, Play(Gaussian(**params), ch))
        else:
            sched += sched.insert(0, Play(self._pulse(**params), ch))

        return sched

    def _extra_metadata(self):
        """
        Creates the metadata for the experiment.
        """
        metadata = []
        for val in self.scanned_values:
            meta = {}
            for qubit in self._qubits:
                ch = DriveChannel(qubit)
                meta[self.scanned_parameter + '.' + ch.name]: val

            metadata.append(meta)

        return metadata
