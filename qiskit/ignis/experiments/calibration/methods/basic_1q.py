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

from typing import Optional

import numpy as np

from qiskit.ignis.experiments.calibration import (cal_base_experiment,
                                                  cal_base_generator,
                                                  cal_base_fitter,
                                                  cal_table,
                                                  sequences,
                                                  types,
                                                  fitters,
                                                  workflow)
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


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
