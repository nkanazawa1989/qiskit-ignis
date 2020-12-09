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


from typing import Optional, List, Tuple

from qiskit.ignis.experiments.calibration import CircuitBasedGenerator
from qiskit.ignis.experiments.calibration.data_processing import DataProcessingSteps
from qiskit.ignis.experiments.calibration.cal_base_analysis import BaseCalibrationAnalysis
from qiskit.ignis.experiments.calibration.instruction_data import InstructionsDefinition
from qiskit.ignis.experiments.calibration.cal_base_experiment import BaseCalibrationExperiment
from qiskit.ignis.experiments.calibration.analysis.trigonometric import CosinusoidalFit

from qiskit.pulse import ControlChannel


class RoughCRAmplitude(BaseCalibrationExperiment):
    """Performs a rough amplitude calibration by scanning the amplitude of the pulse."""

    def __init__(self,
                 inst_def: InstructionsDefinition,
                 qubits: Tuple[int, int],
                 data_processing: DataProcessingSteps,
                 amp_vals: List,
                 cr_name: Optional[str] = 'cr',
                 calibration_group: Optional[str] = 'default',
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        """
        The amplitude of the pulses on the u channel are scanned. The echoed-cr gates with cr90p
        and cr90m will have amplitudes scanned with opposite signs.

        Args:
            inst_def: The class that defines the instructions for this calibration.
            qubits: Qubits of the gate given as (Control, Target).
            data_processing: Steps used to process the data from the Result.
            amp_vals: Amplitude values to scan in the calibration.
            analysis_class: Analysis class used.
            job: Optional job id to retrieve past experiments.
            cr_name: Name of the cross-resonance gate from the instructions definition to use.
        """
        # todo calibration_group is not handled yet
        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = None

        self._name = 'cr_amp'
        self._qubits = qubits  # todo move to base class
        self._inst_def = inst_def  # todo move to base class
        self._calibration_group = calibration_group

        u_ch = inst_def.get_channel(qubits, ControlChannel)

        # Create a list of amp parameters on the control channel and default to global.
        u_ch_inst = inst_def.get_schedule(cr_name, qubits).filter(channels=[u_ch]).instructions
        self._parameter_names = []
        for instruction in u_ch_inst:
            pulse_name, channel, scope_id = instruction[1].name.split('.')
            p_name = inst_def.pulse_parameter_table.get_full_name('amp', pulse_name, u_ch.name,
                                                                  scope_id, calibration_group)

            self._parameter_names.append(p_name)

        qc = inst_def.get_circuit(cr_name, qubits, free_parameter_names=self._parameter_names)
        qc.name = self._parameter_names[0]

        # Create a template in which amplitude(cr90m) = -amplitude(cr90p)
        u_pulse_names = []
        for name in self._parameter_names:
            u_pulse_names.append(name.split('.')[0])

        if 'cr90m' in u_pulse_names and 'cr90p' in u_pulse_names and len(u_pulse_names) == 2:
            params = list(qc.parameters)
            qc.name = 'cr90p'
            if 'cr90p' in params[0].name:
                qc.assign_parameters({params[1]: -params[0]}, inplace=True)
            else:
                qc.assign_parameters({params[0]: -params[1]}, inplace=True)

        generator = CircuitBasedGenerator(
            name=self._name,
            qubits=qubits,
            template_circuit=qc,
            values_to_scan=amp_vals,
            ref_frequency=freq01)

        # setup analysis
        if analysis_class is None:
            analysis_class = CosinusoidalFit(name=generator.name,
                                             data_processing_steps=data_processing)

        super().__init__(generator=generator, analysis=analysis_class, job=job)

    def update_calibrations(self):
        """
        Updates the amplitude of the cr pulses. This can handle cr90p, cr90m.
        """
        if len(self._parameter_names) == 1:
            pulse_name, channel, scope_id, param_name = self._parameter_names[0].split('.')
            tag = self._parameter_names[0] + '.' + self._name
            value = self.analysis.get_fit_function_period_fraction(0.5, self._qubits[1], tag)

            self._inst_def.pulse_parameter_table.set_parameter(
                parameter_name=param_name,
                pulse_name=pulse_name,
                channel=channel,
                scope_id=scope_id,
                value=value,
                calibration_group=self._calibration_group
            )

        if len(self._parameter_names) == 2:
            for full_name in self._parameter_names:
                pulse_name, channel, scope_id, param_name = full_name.split('.')
                if pulse_name[-1] == 'p':
                    tag = pulse_name + '.' + self._name
                    value = self.analysis.get_fit_function_period_fraction(0.5, self._qubits[1], tag)
                else:
                    tag = pulse_name.replace('m', 'p') + '.' + self._name
                    value = -self.analysis.get_fit_function_period_fraction(0.5, self._qubits[1], tag)

                self._inst_def.pulse_parameter_table.set_parameter(
                    parameter_name=param_name,
                    pulse_name=pulse_name,
                    channel=channel,
                    scope_id=scope_id,
                    value=value,
                    calibration_group=self._calibration_group
                )
