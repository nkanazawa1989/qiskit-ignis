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

from collections import defaultdict
from typing import List, Callable, Dict, Union, Iterable

from qiskit import pulse, circuit
from qiskit.circuit import Parameter
from qiskit.ignis.experiments.calibration import types
from qiskit.ignis.experiments.calibration.exceptions import CalExpError


class AtomicGate:
    def __init__(self,
                 name: str,
                 qubits: List[int],
                 channel: pulse.channels.PulseChannel,
                 generator: Callable,
                 param_names: List[str],
                 param_vals: List[types.ParamValue]):
        self.name = name
        self.qubits = qubits
        self.channel = channel
        self.generator = generator
        self.param_names = param_names
        self.param_vals = param_vals

    def __setitem__(self, key: str, value: types.ParamValue):
        try:
            self.param_vals[self.param_names.index(key)] = value
        except ValueError:
            raise Exception('Parameter {pname} is not defined.'.format(pname=key))

    def __getitem__(self, key: str):
        try:
            return self.param_vals[self.param_names.index(key)]
        except ValueError:
            raise Exception('Parameter {pname} is not defined.'.format(pname=key))

    def schedule(self) -> pulse.Schedule:
        """Generate pulse schedule of this atomic instruction."""
        cal_params = dict(zip(self.param_names, self.param_vals))

        sideband = cal_params.pop('sideband', 0)
        phase = cal_params.pop('phase', 0)

        sched = pulse.Schedule(name=self.name)

        # modulate frame
        sched.append(pulse.ShiftPhase(phase, self.channel), inplace=True)
        sched.append(pulse.ShiftFrequency(sideband, self.channel), inplace=True)
        # play pulse
        sched.append(pulse.Play(self.generator(**cal_params, name=self.name), self.channel),
                     inplace=True)
        # recover original frame
        sched.append(pulse.ShiftPhase(-phase, self.channel), inplace=True)
        sched.append(pulse.ShiftFrequency(-sideband, self.channel), inplace=True)

        return sched

    def gate(self) -> circuit.Gate:
        """Generate gate of this atomic instruction."""
        return circuit.Gate(
            name=self.name,
            num_qubits=len(self.qubits),
            params=self.parameters()
        )

    def parametrize(self, param_name: str) -> Parameter:
        """Parametrize pulse parameter with name and return parameter handler."""
        try:
            # assign unique name. this name is used for metadata dict key so not to overlap.
            unique_name = '{inst_name}.{chname}.{pname}'.format(
                inst_name=self.name,
                chname=self.channel.name,
                pname=param_name
            )
            param_obj = Parameter(unique_name)
            self.param_vals[self.param_names.index(param_name)] = param_obj
        except ValueError:
            raise CalExpError('Parameter {name} is not defined'.format(name=param_name))

        return param_obj

    def parameters(self) -> List[Parameter]:
        """Return a list of parameter objects associated with this instruction."""
        return [value for value in self.param_vals if isinstance(value, Parameter)]

    def properties(self) -> Dict[str, types.ParamValue]:
        """Return dictionary of pulse properties."""
        return dict(zip(self.param_names, self.param_vals))


class CalibrationDataTable:

    def __init__(self,
                 backend_name: str,
                 num_qubits: int):
        """Create new table."""
        self._map = defaultdict(lambda: defaultdict(AtomicGate))
        self._backend_name = backend_name
        self._num_qubits = num_qubits

    @property
    def backend_name(self):
        """Return backend name."""
        return self._backend_name

    @property
    def num_qubits(self):
        """Return number of qubits of this system."""
        return self._num_qubits

    def add(self,
            instruction: str,
            qubits: Union[int, Iterable[int]],
            gate: AtomicGate):
        """Add atomic gate instruction to table."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if not isinstance(gate, AtomicGate):
            raise CalExpError('Supplied component must be a CalibrationComponent.')

        self._map[instruction][qubits] = gate

    def has(self,
            instruction: str,
            qubits: Union[int, Iterable[int]]) -> bool:
        """Check if target instruction is defined."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if instruction in self._map and qubits in self._map[instruction]:
            return True
        return False

    def get_gate(self,
                 instruction: str,
                 qubits: Union[int, Iterable[int]]
                 ) -> Union[None, circuit.Gate]:
        """Get atomic gate instruction from table."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if self.has(instruction, qubits):
            return self._map[instruction][qubits].gate()

        return None

    def get_schedule(self,
                     instruction: str,
                     qubits: Union[int, Iterable[int]]
                     ) -> Union[None, pulse.Schedule]:
        """Get atomic gate schedule from table."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if self.has(instruction, qubits):
            return self._map[instruction][qubits].schedule()

        return None

    def get_parameters(self,
                       instruction: str,
                       qubits: Union[int, Iterable[int]]
                       ) -> Union[None, List[Parameter]]:
        """Get atomic gate parameters from table."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if self.has(instruction, qubits):
            return self._map[instruction][qubits].parameters()

        return None

    def get_properties(self,
                       instruction: str,
                       qubits: Union[int, Iterable[int]]
                       ) -> Union[None, Dict[str, types.ParamValue]]:
        """Get atomic gate properties from table."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if self.has(instruction, qubits):
            return self._map[instruction][qubits].properties()

        return None

    def parametrize(self,
                    instruction: str,
                    qubits: Union[int, Iterable[int]],
                    param_name: str) -> Union[None, Parameter]:
        """Parametrize table item and return parameter handler."""
        qubits = CalibrationDataTable._to_tuple(qubits)

        if self.has(instruction, qubits):
            return self._map[instruction][qubits].parametrize(param_name=param_name)

        return None

    @classmethod
    def _to_tuple(cls, qubits: Union[int, Iterable[int]]):
        """A helper function to convert qubits into tuple."""
        try:
            qubits = tuple(qubits)
        except TypeError:
            qubits = (qubits, )

        return qubits
