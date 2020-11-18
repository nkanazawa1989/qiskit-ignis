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

from typing import Optional, Callable

import numpy as np
from qiskit import circuit

from qiskit.ignis.experiments.calibration import (types,
                                                  generators)
from qiskit.ignis.experiments.calibration.data_processing import DataProcessingSteps
from qiskit.ignis.experiments.calibration.cal_base_analysis import BaseCalibrationAnalysis
from qiskit.ignis.experiments.calibration.instruction_data.database import PulseTable
from qiskit.ignis.experiments.calibration.instruction_data import InstructionsDefinition
from qiskit.ignis.experiments.calibration.cal_base_experiment import BaseCalibrationExperiment
from qiskit.ignis.experiments.calibration.analysis.peak import GaussianFit
from qiskit.ignis.experiments.calibration.analysis.trigonometric import CosinusoidalFit


class RoughSpectroscopy(BaseCalibrationExperiment):
    """Performs a frequency spectroscopy by scanning the drive channel frequency."""

    def __init__(self,
                 table: PulseTable,
                 qubit: int,
                 data_processing: DataProcessingSteps,
                 freq_vals: np.ndarray,
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None,
                 pulse_envelope: Optional[Callable] = None,
                 pulse_name: Optional[str] = types.SingleQubitPulses.XP.value):
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
        param_dict = table.get_instruction_kwargs(
            qubits=qubit,
            channel='d*',
            inst_name=pulse_name
        )

        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = circuit.Parameter('q{ind}.d{ind}.f01'.format(ind=qubit))

        generator = generators.SinglePulseGenerator(
            name='spectroscopy',
            qubit=qubit,
            parameters=param_dict,
            values_to_scan=freq_vals,
            ref_frequency=freq01,
            pulse_envelope=pulse_envelope)

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
                 amp_vals: np.ndarray,
                 pulse_name: str,
                 pulse_shape: str,
                 analysis_class: Optional[BaseCalibrationAnalysis] = None,
                 job: Optional = None):
        """Create new rabi amplitude experiment.

        Args:
            table: The table of pulse parameters.
            inst_def: The class that defines the instructions for this calibration.
            qubit: Qubit on which to run the calibration.
            data_processing: Steps used to process the data from the Result.
            amp_vals: Amplitude values to scan in the calibration.
            analysis_class: Analysis class used.
            job: Optional job id to retrieve past experiments.
            pulse_name: Pulse name in the database entry to provide parameter set to
                construct pulse schedule to calibrate. By default pi pulse parameter is used.
        """

        # todo get qubit property from other database.
        # channel ref frequency is different from pulse sideband and thus
        # this value is stored in another relational database.
        # something like qubit property table where f01, anharmonicity, T1, T2, etc... exist.
        freq01 = None

        pname = pulse_name + '.d%i.' % qubit + pulse_shape + '.amp'

        generator = generators.CircuitBasedGenerator(
            name='power_Rabi',
            qubit=qubit,
            template_circuit=inst_def.get_circuit(pulse_name, (qubit, ), free_parameter_names=[pname]),
            values_to_scan=amp_vals,
            ref_frequency=freq01)

        # setup analysis
        if analysis_class is None:
            analysis_class = CosinusoidalFit(name=generator.name,
                                             data_processing_steps=data_processing)

        super().__init__(generator=generator,
                         analysis=analysis_class,
                         job=job)
