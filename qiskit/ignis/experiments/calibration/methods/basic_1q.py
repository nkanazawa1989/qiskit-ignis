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
from qiskit.ignis.experiments.base import Analysis
from qiskit.ignis.experiments.calibration import (cal_base_experiment,
                                                  cal_base_generator,
                                                  cal_table,
                                                  sequences,
                                                  types,
                                                  workflow)
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class RoughAmplitudeCalibration(cal_base_experiment.BaseCalibrationExperiment):

    # pylint: disable=arguments-differ
    def __init__(self,
                 table: cal_table.CalibrationDataTable,
                 qubit: int,
                 amp_vals: np.ndarray,
                 analysis: Optional[Analysis] = None,
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

        # setup generator
        generator = cal_base_generator.BaseCalibrationGenerator(
            cal_name='rough_amplitude',
            target_qubits=[qubit],
            cal_generator=sequences.rabi,
            table=table,
            meas_basis='z'
        )
        generator.assign_parameters({amp: amp_vals})

        super().__init__(generator=generator,
                         analysis=analysis,
                         job=job)
