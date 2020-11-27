from typing import Iterable, Optional, Union, List

from qiskit import QuantumCircuit

from qiskit.ignis.experiments.calibration.cal_base_generator import Base1QCalibrationGenerator


class CircuitBasedGenerator(Base1QCalibrationGenerator):
    """
    A base generator.
    """

    def __init__(self,
                 name: str,
                 qubit: int,
                 template_circuit: QuantumCircuit,
                 values_to_scan: Iterable[float],
                 ref_frequency: Optional[float] = None):
        super().__init__(name=name,
                         qubit=qubit,
                         parameters=template_circuit.parameters,
                         values_to_scan=values_to_scan,
                         ref_frequency=ref_frequency)

        self._template_qcs = [template_circuit]

    def template_qcs(self) -> List[QuantumCircuit]:
        """Return the template quantum circuits."""
        return self._template_qcs
