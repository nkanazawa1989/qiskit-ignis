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


class RoughCRAmplitude(BaseCalibrationExperiment):
    """Performs a rough amplitude calibration by scanning the amplitude of the pulse."""

    def __init__(self,
                 inst_def: InstructionsDefinition,
                 qubits: Tuple[int, int],
                 data_processing: DataProcessingSteps,
                 amp_vals: List,
                 pulse_names: List[str],
                 cr_name: Optional[str] = 'cr',
                 calibration_group: Optional[str] = 'default',
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        """Create new rabi amplitude experiment.
        Args:
            inst_def: The class that defines the instructions for this calibration.
            qubits: Qubits of the gate given as (Control, Target).
            data_processing: Steps used to process the data from the Result.
            amp_vals: Amplitude values to scan in the calibration.
            analysis_class: Analysis class used.
            job: Optional job id to retrieve past experiments.
            cr_name: Name of the cross-resonance gate from the instructions definition to use.
            pulse_names: Pulse names in the database entry to provide parameter set to
                construct pulse schedule to calibrate. By default pi pulse parameter is used.
        """

        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = None

        u_ch = inst_def.get_channel_name(qubits)

        free_names = []
        for pulse_name in pulse_names:
            scope_id = inst_def.get_scope_id(cr_name, qubits)
            free_names.append('%s.%s.%s.amp' % (pulse_name, u_ch, scope_id))

        template_circ = inst_def.get_circuit('xp', (qubits[0], ))
        template_circ.compose(inst_def.get_circuit(cr_name, qubits,
                                                   free_parameter_names=free_names), inplace=True)

        # Create a template in which amplitude(cr90m) = -amplitude(cr90p)
        if 'cr90m' in pulse_names and 'cr90p' in pulse_names and len(pulse_names) == 2:
            params = list(template_circ.parameters)
            template_circ.assign_parameters({params[1]: -params[0]}, inplace=True)

        generator = CircuitBasedGenerator(
            name='cr_amp',
            qubits=qubits,
            template_circuit=template_circ,
            values_to_scan=amp_vals,
            ref_frequency=freq01)

        # setup analysis
        if analysis_class is None:
            analysis_class = CosinusoidalFit(name=generator.name,
                                             data_processing_steps=data_processing)

        super().__init__(generator=generator, analysis=analysis_class, job=job)
