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

from typing import Optional, Callable, List

from qiskit.pulse import DriveChannel

from qiskit.ignis.experiments.calibration import CircuitBasedGenerator
from qiskit.ignis.experiments.calibration.data_processing import DataProcessingSteps
from qiskit.ignis.experiments.calibration.cal_base_analysis import BaseCalibrationAnalysis
from qiskit.ignis.experiments.calibration.instruction_data import InstructionsDefinition
from qiskit.ignis.experiments.calibration.cal_base_experiment import BaseCalibrationExperiment
from qiskit.ignis.experiments.calibration.analysis.peak import GaussianFit
from qiskit.ignis.experiments.calibration.analysis.trigonometric import CosinusoidalFit


class RoughSpectroscopy(BaseCalibrationExperiment):
    """Performs a frequency spectroscopy by scanning the drive channel frequency."""

    def __init__(self,
                 inst_def: InstructionsDefinition,
                 qubit: int,
                 data_processing: DataProcessingSteps,
                 freq_vals: List,
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None,
                 pulse_envelope: Optional[Callable] = None,
                 pulse_name: Optional[str] = ''):
        """Create new spectroscopy experiment.

        Args:
            table: The table of pulse parameters.
            qubit: Qubit on which to run the calibration.
            data_processing: Steps used to process the data from the Result.
            freq_vals: Frequency values to scan in the calibration.
            analysis_class: Analysis class used.
            job: Optional job id to retrive past expereiments.
            pulse_envelope: Name of the pulse function used to generate the
                pulse schedule. If not specified, the default pulse shape of
                :py:class:`SinglePulseGenerator` is used.
            pulse_name: Pulse name in the database entry to provide parameter set to
                construct pulse schedule to calibrate. By default pi pulse parameter is used.
        """

        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = 0.0

        generator = CircuitBasedGenerator(
            name='spectroscopy',
            qubit=qubit,
            template_circuit=inst_def.get_circuit(pulse_name, (qubit, )),
            values_to_scan=freq_vals,
            ref_frequency=freq01)

        # setup analysis
        if analysis_class is None:
            analysis_class = GaussianFit(name=generator.name)

        super().__init__(generator=generator,
                         analysis=analysis_class,
                         job=job)


class RoughAmplitudeCalibration(BaseCalibrationExperiment):
    """Performs a rough amplitude calibration by scanning the amplitude of the pulse."""

    def __init__(self,
                 inst_def: InstructionsDefinition,
                 qubit: int,
                 data_processing: DataProcessingSteps,
                 amp_vals: List,
                 gate_name: str,
                 calibration_group: Optional[str] = 'default',
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        """Create new rabi amplitude experiment.

        Args:
            inst_def: The class that defines the instructions for this calibration.
            qubit: Qubit on which to run the calibration.
            data_processing: Steps used to process the data from the Result.
            amp_vals: Amplitude values to scan in the calibration.
            gate_name: Pulse name in the database entry to provide parameter set to
                construct pulse schedule to calibrate. By default pi pulse parameter is used.
            analysis_class: Analysis class used.
            job: Optional job id to retrieve past experiments.
        """
        self._name = 'power_rabi'

        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = None

        scope_id = inst_def.get_scope_id(gate_name, (qubit,))
        ch_name = inst_def.get_channel((qubit,), DriveChannel).name
        p_name = inst_def.pulse_parameter_table.get_full_name('amp', gate_name, ch_name, scope_id)

        template_qc = inst_def.get_circuit(gate_name, (qubit, ), free_parameter_names=[p_name])
        template_qc.name = 'circuit'

        generator = CircuitBasedGenerator(
            name=self._name,
            qubits=[qubit],
            template_circuit=template_qc,
            values_to_scan=amp_vals,
            ref_frequency=freq01)

        # setup analysis
        if analysis_class is None:
            analysis_class = CosinusoidalFit(name=generator.name,
                                             data_processing_steps=data_processing)

        self.qubit = qubit  # todo move to base class
        self._inst_def = inst_def  # todo move to base class
        self._parameter_name = p_name  # todo move to base class?
        self._calibration_group = calibration_group

        super().__init__(generator=generator, analysis=analysis_class, job=job)

    def update_calibrations(self):
        """
        Updates the amplitude of the xp pulse.
        """
        pulse_name, channel, scope_id, param_name = self._parameter_name.split('.')
        tag = 'circuit.'+self._name
        value = self.analysis.get_fit_function_period_fraction(0.5, self.qubit, tag)

        self._inst_def.pulse_parameter_table.set_parameter(
            parameter_name=param_name,
            pulse_name=pulse_name,
            channel=channel,
            scope_id=scope_id,
            value=value,
            calibration_group=self._calibration_group
        )
