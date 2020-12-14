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

from qiskit.circuit import QuantumCircuit, Parameter

from qiskit.ignis.experiments.base import Generator
from qiskit.ignis.experiments.calibration import cal_metadata
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class CircuitBasedGenerator(Generator):
    """
    A base generator for single-qubit calibration. All circuits
    generated from this generator will apply to a single qubit. 
    """

    def __init__(self,
                 name: str,
                 qubits: List[int],
                 template_circuit: QuantumCircuit,
                 values_to_scan: Iterable[float],
                 ref_frequency: Optional[float] = None):
        """
        Args:
            qubits: The qubits to which we will add the calibration.
            values_to_scan: A list of parameter values for which to generate circuits.
            ref_frequency: A reference frequency of drive channel to run calibration.
                Usually this is identical to the qubit frequency, or f_01.
                The drive channel is initialized with this frequency and
                shift frequency instruction of consecutive pulses, or pulse sideband,
                are modulated with respect to this frequency.
        """
        super().__init__(name=name, qubits=qubits)
        self._scanned_values = values_to_scan
        self._ref_frequency = ref_frequency

        template_circuit.measure(qubits, qubits)

        self._template_qcs = [template_circuit]

        if not self._is_1d_scan():
            raise CalExpError('Generator is a 1D scan. Free parameters: {}.'.format(', '.join(map(str, self.parameters))))

    def _is_1d_scan(self) -> bool:
        """Restrict this class to 1D scans."""
        if len(self.parameters) != 1:
            return False

        return True

    @property
    def parameters(self):
        """Returns the list of parameters that the generator uses."""
        parameters = set()
        for qc in self.template_qcs():
            for parameter in qc.parameters:
                parameters.add(parameter)

        return parameters

    def template_qcs(self) -> List[QuantumCircuit]:
        """Create the template quantum circuit(s)."""
        return self._template_qcs

    def circuits(self) -> List[QuantumCircuit]:
        """
        Return a list of circuits that are run in the calibration experiment.
        Each circuit corresponds to one of the specified parameter values.
        This function is also responsible for adding the
        meta data to the circuits.
        """
        cal_circs = []
        for template_qc in self.template_qcs():
            parameter = list(template_qc.parameters)[0]
            for val in self._scanned_values:
                cal_circs.append(template_qc.assign_parameters({parameter: val}))

        return cal_circs

    def _extra_metadata(self):
        """
        Creates the metadata for the experiment.
        """
        metadata = []
        for template_qc in self.template_qcs():
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
