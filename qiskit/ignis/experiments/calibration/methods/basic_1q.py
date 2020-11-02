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

from qiskit.ignis.experiments.calibration import (cal_base_generator,
                                                  cal_table,
                                                  sequences,
                                                  types,
                                                  fitters,
                                                  workflow)
from qiskit.ignis.experiments.calibration import BaseCalibrationExperiment
from qiskit.ignis.experiments.calibration import CalibrationMetadata, Calibration1DAnalysis
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
                 analysis: Optional[Calibration1DAnalysis] = None,
                 job: Optional = None):
        entry = types.SingleQubitAtomicPulses.STIM.value

        if not table.has(instruction=entry, qubits=[qubit]):
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


class RoughAmplitudeCalibration(BaseCalibrationExperiment):
    """Performs a rough amplitude calibration by scanning the amplitude of the pulse."""

    # pylint: disable=arguments-differ
    def __init__(self,
                 table: cal_table.CalibrationDataTable,
                 qubit: int,
                 data_processing: workflow.AnalysisWorkFlow,
                 amp_vals: np.ndarray,
                 pulse_params: dict,
                 analysis: Optional[Calibration1DAnalysis] = None,
                 job: Optional = None,
                 pulse_envelope: Optional[Callable] = Gaussian):
        """
        Args:
            table:
            qubit: Qubit on which to run the calibration.
            data_processing: Steps used to process the data from the Result.
            amp_vals: Amplitude values to scan in the calibration.
            pulse_params: Parameters of the pulse. These need to match the
                definition of the pulse_envelope being used.
            analysis: Analysis class used.
            job: Optional job id to retrive past expereiments.
            pulse_envelope: Name of the pulse function used to generate the
                pulse schedule.
        """
        entry = types.SingleQubitAtomicPulses.STIM.value

        if not table.has(instruction=entry, qubits=[qubit]):
            raise CalExpError('Entry {name} does not exist. '
                              'Check your calibration table.'.format(name=entry))

        # parametrize table
        amp = table.parametrize(
            instruction=entry,
            qubits=[qubit],
            param_name='amp'
        )

        # Store the parameters in the table.
        for key, val in pulse_params.items():
            table.set_parameter(
                instruction=entry,
                qubits=[qubit],
                param_name=key,
                param_value=val
            )

        generator = SinglePulseGenerator(qubit, pulse_params, amp_vals, amp, 'Rabi', pulse_envelope)

        # setup analysis
        if analysis is None:
            analysis = fitters.CosinusoidalFit(name=generator.name)

        analysis.parameter = amp

        super().__init__(generator=generator,
                         analysis=analysis,
                         job=job,
                         workflow=data_processing)


class SinglePulseGenerator(Generator):
    """
    A generator that generates single pulses and scans a single parameter
    of that pulse. Note that the same pulse may be applied to multiple qubits
    to perform simultaneous calibration.
    """

    def __init__(self,
                 qubit: int,
                 parameters: Dict,
                 values_to_scan: Union[List, np.array],
                 scanned_parameter: Parameter,
                 name: str,
                 pulse: Callable = None):
        """
        Args:
            qubit: The qubit to which we will add the calibration.
            parameters: The arguments for the pulse schedule.
            values_to_scan: A list of amplitudes for which to generate a circuit.
            scanned_parameter: Name of the scanned parameter. If it is not present
                in the parameters dictionary as a ParameterExpression it will
                be added to this dict.
            pulse: A parametric pulse function used to generate the schedule
                that is added to the circuits. This defaults to Gaussian and
                parameters should contain 'duration', and 'sigma'.
        """
        super().__init__(name, [0])
        self._pulse = pulse
        self.parameters = parameters
        self.scanned_values = values_to_scan
        self.scanned_parameter = scanned_parameter
        self.qubit = qubit

        # The name of the pulse parameter is the last entry
        name = self.scanned_parameter.name.split('.')[-1]
        self.parameters[name] = scanned_parameter

        # Define the QuantumCircuit that this generator will use.
        self.template_qcs = []
        qc = QuantumCircuit(1, 1)
        gate = Gate(scanned_parameter.name, 1, [scanned_parameter])
        qc.append(gate, [0])
        qc.add_calibration(gate, [self.qubit], self._schedule(), scanned_parameter)
        qc.measure(0, 0)
        self.template_qcs.append(qc)

    def circuits(self) -> List[QuantumCircuit]:
        """
        Return a list of experiment circuits.
        This function is also responsible for adding the
        meta data to the circuits.
        """
        qc = self.template_qcs[0]
        return [qc.assign_parameters({self.scanned_parameter: val})
                for val in self.scanned_values]

    def _schedule(self) -> Schedule:
        """
        Creates the schedules that will be added to the circuit.
        """
        sched = Schedule(name=self.scanned_parameter.name)
        ch = DriveChannel(self.qubit)

        # TODO Some backends apparently don't support SetPhase
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
            x_values = {
                self.scanned_parameter.name: val
            }
            meta = CalibrationMetadata(name=self.name, x_values=x_values)
            metadata.append(meta.to_dict())

        return metadata
