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

"""Calibration generators for single qubits."""


from typing import Optional, List, Callable, Union, Dict, Iterable

import numpy as np

from qiskit import circuit, pulse
from qiskit.ignis.experiments.calibration import cal_base_generator


class SinglePulseGenerator(cal_base_generator.Base1QCalibrationGenerator):
    """
    A generator that generates single pulses and scans a single parameter
    of that pulse. Note that the same pulse may be applied to multiple qubits
    to perform simultaneous calibration.
    """
    def __init__(self,
                 name: str,
                 qubit: int,
                 parameters: Dict[str, Union[int, float, complex, circuit.Parameter]],
                 values_to_scan: Iterable[float],
                 ref_frequency: Optional[Union[float, circuit.Parameter]] = None,
                 pulse_envelope: Optional[Callable] = None):
        """
        Args:
            name: Name of this experiment.
            qubit: The qubit to which we will add the calibration.
            parameters: The arguments for the pulse schedule.
            values_to_scan: A list of parameter values for which to generate a circuit.
            ref_frequency: A reference frequency of drive channel to run calibration.
                Usually this is identical to the qubit frequency, or f_01.
                The drive channel is initialized with this frequency and
                shift frequency instruction of consecutive pulses, or pulse sideband,
                are modulated with respect to this frequency.
            pulse_envelope: A parametric pulse function used to generate the schedule
                that is added to the circuits. This defaults to Gaussian and
                parameters should contain `duration`, `amp`, and `sigma`.
        """
        self._pulse_envelope = pulse_envelope

        super().__init__(name=name,
                         qubit=qubit,
                         parameters=parameters,
                         values_to_scan=values_to_scan,
                         ref_frequency=ref_frequency)

    def _template_qcs(self) -> List[circuit.QuantumCircuit]:
        """Create the template quantum circuit.
        """
        cal_sched = self.single_pulse_schedule()
        parameter = list(cal_sched.parameters)[0]

        template_qc = circuit.QuantumCircuit(1, 1, name='single_pulse')
        gate = circuit.Gate(parameter.name, 1, [parameter])
        template_qc.append(gate, [0])
        template_qc.add_calibration(gate, self.qubits, cal_sched, parameter)
        template_qc.measure(0, 0)

        return [template_qc]

    def single_pulse_schedule(self) -> pulse.Schedule:
        """
        Creates the schedules that will be added to the circuit.
        """
        with pulse.build() as sched:
            d_channel = pulse.DriveChannel(self.qubits[0])
            # initialize channel frequency
            if self._ref_frequency is not None:
                pulse.set_frequency(self._ref_frequency, d_channel)
            # add single stimulus pulse
            if not self._pulse_envelope:
                # remove DRAG coefficient if exists
                self._parameters.pop('beta', None)
                pulse.play(pulse.Gaussian(**self._parameters), d_channel)
            else:
                pulse.play(self._pulse_envelope(**self._parameters), d_channel)

        return sched


class RamseyXYGenerator(cal_base_generator.Base1QCalibrationGenerator):
    """
    todo docstring
    """
    def __init__(self,
                 name: str,
                 qubit: int,
                 parameters: Dict[str, Union[int, float, complex]],
                 delays: Iterable[float],
                 ref_frequency: Optional[float] = None,
                 pulse_envelope: Optional[Callable] = None):
        """
        Args:
            name: Name of this experiment.
            qubit: The qubit to which we will add the calibration.
            parameters: The arguments for the pulse schedule that creates X90 pulse.
            delays: A list of delay values for which to generate a circuit.
            ref_frequency: A reference frequency of drive channel to run calibration.
                Usually this is identical to the qubit frequency, or f_01.
                The drive channel is initialized with this frequency and
                shift frequency instruction of consecutive pulses, or pulse sideband,
                are modulated with respect to this frequency.
            pulse_envelope: A parametric pulse function used to generate the schedule
                that is added to the circuits. This defaults to Drag and
                parameters should contain `duration`, `amp`, `sigma` and `beta`.
        """
        self._pulse_envelope = pulse_envelope
        self._delay = circuit.Parameter('q{ind}.d{ind}.delay'.format(ind=qubit))

        super().__init__(name=name,
                         qubit=qubit,
                         parameters=parameters,
                         values_to_scan=delays,
                         ref_frequency=ref_frequency)

    def _template_qcs(self) -> List[circuit.QuantumCircuit]:
        """Create the template quantum circuit.
        """
        cal_series = {'x': self.ramsey_x_schedule(), 'y': self.ramsey_y_schedule()}

        template_qcs = []
        for key, sched in cal_series.items():
            template_qc = circuit.QuantumCircuit(1, 1, name=key)
            gate = circuit.Gate(self._delay.name, 1, [self._delay])
            template_qc.append(gate, [0])
            template_qc.add_calibration(gate, self.qubits, sched, self._delay)
            template_qc.measure(0, 0)
            template_qcs.append(template_qc)

        return template_qcs

    def ramsey_x_schedule(self) -> pulse.Schedule:
        """
        Creates Ramsey sequence with X90-X90 pulse.
        """
        with pulse.build() as sched:
            d_channel = pulse.DriveChannel(self.qubits[0])
            # initialize channel frequency
            if self._ref_frequency is not None:
                pulse.set_frequency(self._ref_frequency, d_channel)

            # add x90 pulse
            if not self._pulse_envelope:
                pulse.play(pulse.Drag(**self._parameters), d_channel)
            else:
                pulse.play(self._pulse_envelope(**self._parameters), d_channel)

            # todo perhaps this doesn't work because delay doesn't accept float.
            # circuit parameter cannot be automatically cast into integer.
            pulse.delay_qubits(self._delay, self.qubits[0])

            # add x90 pulse
            if not self._pulse_envelope:
                pulse.play(pulse.Drag(**self._parameters), d_channel)
            else:
                pulse.play(self._pulse_envelope(**self._parameters), d_channel)

        return sched

    def ramsey_y_schedule(self) -> pulse.Schedule:
        """
        Creates Ramsey sequence with X90-Y90 pulse.
        """
        with pulse.build() as sched:
            d_channel = pulse.DriveChannel(self.qubits[0])
            # initialize channel frequency
            if self._ref_frequency is not None:
                pulse.set_frequency(self._ref_frequency, d_channel)

            # add x90 pulse
            if not self._pulse_envelope:
                pulse.play(pulse.Drag(**self._parameters), d_channel)
            else:
                pulse.play(self._pulse_envelope(**self._parameters), d_channel)

            # todo perhaps this doesn't work because delay doesn't accept float.
            # circuit parameter cannot be automatically cast into integer.
            pulse.delay_qubits(self._delay, self.qubits[0])

            # add y90 pulse
            pulse.shift_phase(np.pi/2, d_channel)
            if not self._pulse_envelope:
                pulse.play(pulse.Drag(**self._parameters), d_channel)
            else:
                pulse.play(self._pulse_envelope(**self._parameters), d_channel)

        return sched
