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

"""Local database interface.

# TODO add detailed description of databases.
"""

from enum import Enum
from typing import Dict, Union, Iterable, Optional, List

from qiskit import pulse, circuit
from qiskit.providers.ibmq import IBMQBackend
from qiskit.qobj.converters.pulse_instruction import ParametricPulseShapes
from qiskit.ignis.experiments.calibration.instruction_data.database import (PulseTable,
                                                                            ScheduleTemplate)
from qiskit.ignis.experiments.calibration.instruction_data import utils


class InstructionSet:
    def __init__(self,
                 backend_name: str,
                 pulse_table: Optional[PulseTable] = None,
                 schedule_template: Optional[ScheduleTemplate] = None,
                 parameter_library: Optional[Dict[str, circuit.Parameter]] = None,
                 parametric_shapes: Optional[Enum] = None):
        """Create new instruction set.

        Args:
            backend_name: Name of backend that this database is associated with.
            pulse_table: Database for pulse parameters.
            schedule_template: Database for pulse program.
            parameter_library: Collection of previously defined parameters.
            parametric_shapes: Enumerator of pulse shape name and ParametricPulse subclass.
        """
        self._backend_name = backend_name
        self._parameter_library = parameter_library or dict()

        self._pulse_table = pulse_table or PulseTable()
        self._schedule_template = schedule_template or ScheduleTemplate()
        self._parametric_shapes = parametric_shapes or ParametricPulseShapes

    @classmethod
    def from_backend(cls, backend: IBMQBackend) -> 'InstructionSet':
        """A factory method that creates InstructionSet from IBMQ backend.

        Args:
            backend: IBMQ backend or other pulse backends that conform to OpenPulse spec.

        Returns:
            New InstructionSet instance.
        """
        parameter_library = dict()

        pulse_table, sched_template = utils.parse_backend_instmap(
            instmap=backend.defaults(refresh=True).instruction_schedule_map,
            parameter_library=parameter_library)

        return InstructionSet(
            backend_name=backend.name(),
            pulse_table=pulse_table,
            schedule_template=sched_template,
            parameter_library=parameter_library)

    def update_remote_database(self):
        """Update remote database."""
        raise NotImplementedError

    @property
    def pulse_table(self):
        """Return pulse table database."""
        return self._pulse_table

    @property
    def schedule_template(self):
        """Return schedule template database."""
        return self._schedule_template

    @property
    def backend_name(self):
        """Return name of backend associated with this database."""
        return self._backend_name

    def get_gate_schedule(self,
                          qubits: Union[int, Iterable[int]],
                          name: str,
                          stretch_factor: float = 1.0) -> pulse.Schedule:
        """Get specified schedule from database.

        Args:
            qubits: Index of qubits.
            name: Name of gate.
            stretch_factor: Stretch factor of the pulse, typically used for error mitigation.

        Returns:
            Pulse schedule of specified gate.
        """
        temp_sched = self.schedule_template.get_template_schedule(qubits, name)

        return utils.compose_schedule(
            qubits=qubits,
            template_sched=temp_sched,
            pulse_table=self.pulse_table,
            stretch_factor=stretch_factor,
            parametric_shapes=self._parametric_shapes
        )

    def add_gate_schedule(self,
                          qubits: Union[int, Iterable[int]],
                          name: str,
                          schedule: pulse.Schedule,
                          stretch_factor: float = 1.0):
        """Add new schedule to database.

        Args:
            qubits: Index of qubits.
            name: Name of gate that the schedule implements.
            schedule: Calibrated schedule to implement the gate.
            stretch_factor: Stretch factor of the pulse, typically used for error mitigation.
        """
        temp_sched = utils.decompose_schedule(
            qubits=qubits,
            gate_sched=schedule,
            pulse_table=self.pulse_table,
            parameter_library=self._parameter_library,
            stretch_factor=stretch_factor,
            parametric_shapes=self._parametric_shapes
        )
        self.schedule_template.set_template_schedule(qubits, name, temp_sched)

    def instruction_schedule_map(self, stretch_factor=1.0) -> pulse.InstructionScheduleMap:
        """Create instruction schedule map based on calibrated instruction set.

        Args:
            stretch_factor: Stretch factor of the pulse, typically used for error mitigation.

        Returns:
            An instruction schedule map supplied to Qiskit scheduler.
        """
        instmap = pulse.InstructionScheduleMap()

        for _, entry in self.schedule_template.filter_data().iterrows():
            composed_sched = utils.compose_schedule(
                qubits=entry.qubits,
                template_sched=entry.schedule,
                pulse_table=self.pulse_table,
                stretch_factor=stretch_factor,
                parametric_shapes=self._parametric_shapes
            )
            instmap.add(instruction=entry.gate_name,
                        qubits=entry.qubits,
                        schedule=composed_sched)

        return instmap

    def basis_gates(self, removes: Optional[List[str]] = None) -> List[str]:
        """Create basis gate list based on stored schedules.

        Args:
            removes: Name of removed instructions. `measure` is demoved by default.

        Returns:
            A list of basis gates supplied to Qiskit transpiler.
        """
        if removes is None:
            removes = ['measure']
        else:
            removes = list(removes)
        instmap = self.instruction_schedule_map()

        return [gate for gate in instmap.instructions if gate not in removes]
