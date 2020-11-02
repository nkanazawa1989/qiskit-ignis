from typing import Union, List
from dataclasses import dataclass


@dataclass
class CalibrationMetadata:
    """
    This class defines the structure of the meta data that describes
    calibration experiments. Calibration analysis routines will
    use variables of this class to tie together the results from
    different quantum circuits.
    """

    # The name of the calibration experiment.
    name: str = None

    # Name of the pulse schedule that was used in the calibration experiment.
    pulse_schedule_name: str = None

    # A dictionary of x-values the structure of this dict will
    # depend on the experiment being run.
    x_values: dict = None

    # The series of the Experiment to which the circuit is
    # attached to. E.g. 'X' or 'Y' for Ramsey measurements.
    series: Union[str, int, float] = None

    # ID of the experiment to which this circuit is attached.
    exp_id: str = None

    # Physical qubits used.
    qubits: List[int] = None

    def to_dict(self) -> dict:
        """Export the meta data to a dict structure."""
        return {
            'name': self.name,
            'series': self.series,
            'x_values': self.x_values,
            'pulse_schedule_name': self.pulse_schedule_name
        }
