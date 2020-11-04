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

"""Qiskit Ignis calibration generator."""

from typing import Union, Dict, List, Iterable, Optional

from qiskit import circuit

from qiskit.ignis.experiments.base import Generator
from qiskit.ignis.experiments.calibration import cal_metadata


class Base1QCalibrationGenerator(Generator):
    """
    A base generator for single-qubit calibration. All circuits
    generated from this generator will apply to a single qubit. 
    """

    def __init__(self,
                 name: str,
                 qubit: int,
                 parameters: Dict[str, Union[int, float, complex, circuit.Parameter]],
                 values_to_scan: Iterable[float],
                 ref_frequency: Optional[float] = None):
        """
        Args:
            qubit: The qubit to which we will add the calibration.
            parameters: The arguments for the pulse schedule.
            values_to_scan: A list of amplitudes for which to generate a circuit.
            ref_frequency: A reference frequency of drive channel to run calibration.
                Usually this is identical to the qubit frequency, or f_01.
                The drive channel is initialized with this frequency and
                shift frequency instruction of consecutive pulses, or pulse sideband,
                are modulated with respect to this frequency.
        """
        super().__init__(name=name, qubits=[qubit])
        self._parameters = parameters
        self._scanned_values = values_to_scan
        self._ref_frequency = ref_frequency

    def _template_qcs(self) -> List[circuit.QuantumCircuit]:
        """Create the template quantum circuit.
        """
        raise NotImplementedError

    def circuits(self) -> List[circuit.QuantumCircuit]:
        """
        Return a list of experiment circuits.
        This function is also responsible for adding the
        meta data to the circuits.
        """
        cal_circs = []
        for template_qc in self._template_qcs():
            parameter = list(template_qc.parameters)[0]
            for val in self._scanned_values:
                cal_circs.append(template_qc.assign_parameters({parameter: val}))

        return cal_circs

    def _extra_metadata(self):
        """
        Creates the metadata for the experiment.
        """
        metadata = []
        for template_qc in self._template_qcs():
            parameter = list(template_qc.parameters)[0]
            for val in self._scanned_values:
                x_values = {
                    parameter.name: val
                }
                meta = cal_metadata.CalibrationMetadata(
                    name=self.name,
                    series=template_qc.name,
                    pulse_schedule_name=self.__class__.__name__,
                    x_values=x_values
                )
                metadata.append(meta.to_dict())

        return metadata
