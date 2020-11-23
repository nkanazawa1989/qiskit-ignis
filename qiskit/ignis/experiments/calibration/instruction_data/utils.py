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

"""Utilities for database."""

from copy import deepcopy
from enum import Enum
from typing import Optional, Tuple, Dict

import numpy as np
from qiskit.qobj.converters.pulse_instruction import ParametricPulseShapes

from qiskit import pulse, circuit
from qiskit.ignis.experiments.calibration.exceptions import CalExpError
from qiskit.ignis.experiments.calibration.instruction_data.database import (PulseTable,
                                                                            ScheduleTemplate)


def compose_schedule(
        channel_qubit_map: Dict[str, Tuple[int]],
        template_sched: pulse.Schedule,
        pulse_table: PulseTable,
        stretch_factor: float,
        parametric_shapes: Optional[Enum] = None
        ) -> pulse.Schedule:
    """A helper function to compose an executable schedule by binding parameters from
    :py:class:`PulseTable`.

    Args:
        channel_qubit_map: A map between pulse channel string and qubit index.
        template_sched: Parametrized schedule template.
        pulse_table: PulseTable where pulse parameters are stored.
        stretch_factor: Stretch factor of the pulse, typically used for error mitigation.
        parametric_shapes: Enum object that maps pulse name and ParametricPulse.

    Returns:
        Pulse schedule with bound parameters.
    """
    if not parametric_shapes:
        parametric_shapes = ParametricPulseShapes

    gate_sched = pulse.Schedule(name=template_sched.name)
    for t0, sched_component in template_sched.instructions:
        if isinstance(sched_component, pulse.Play) and sched_component.is_parameterized():
            # bind parameters if parametric pulse entry
            pulse_data = sched_component.pulse

            # get pulse shape type
            try:
                pulse_type = parametric_shapes(pulse_data.__class__).name
            except ValueError:
                pulse_type = pulse_data.__class__.__name__

            # get qubit index
            if sched_component.channel.name in channel_qubit_map:
                qubits = tuple(channel_qubit_map[sched_component.channel.name])
            else:
                raise CalExpError('Qubits associated with channel {chname} is not defined.'
                                  ''.format(chname=sched_component.channel.name))

            # get parameters from pulse table
            pulse_params = pulse_table.get_instruction_kwargs(
                qubits=qubits,
                channel=sched_component.channel.name,
                inst_name=sched_component.name,
                pulse_type=pulse_type,
                stretch_factor=stretch_factor)

            binds = dict()
            for pobj in sched_component.parameters:
                # bind parameter values if defined in the pulse table
                if pobj.name in pulse_params:
                    binds[pobj] = pulse_params[pobj.name]
            sched_component = deepcopy(sched_component).assign_parameters(binds)

        gate_sched.insert(t0, sched_component, inplace=True)

    return gate_sched


def decompose_schedule(
        channel_qubit_map: Dict[str, Tuple[int]],
        gate_sched: pulse.Schedule,
        pulse_table: PulseTable,
        parameter_library: Dict[str, circuit.Parameter],
        stretch_factor: float,
        parametric_shapes: Optional[Enum] = None
        ) -> pulse.Schedule:
    """A helper function to decompose a gate schedule into template schedule and parameters.
    Decoupled parameters are stored in :py:class:`PulseTable`.

    Args:
        channel_qubit_map: A map between pulse channel string and qubit index.
        gate_sched: Schedule that implements specific quantum gate.
        pulse_table: PulseTable where pulse parameters are stored.
        parameter_library: Collection of previously defined parameters.
        stretch_factor: Stretch factor of the pulse, typically used for error mitigation.
        parametric_shapes: Enum objet that maps pulse name and ParametricPulse.

    Returns:
        Pulse schedule with bound parameters.
    """
    if not parametric_shapes:
        parametric_shapes = ParametricPulseShapes

    template_sched = pulse.Schedule(name=gate_sched.name)
    for t0, sched_component in gate_sched.instructions:
        if isinstance(sched_component, pulse.Play) \
                and isinstance(sched_component.pulse, pulse.ParametricPulse):
            # decouple parameters if parametric pulse entry
            pulse_data = sched_component.pulse
            parameter_kwargs = {}

            # get pulse shape type
            try:
                pulse_type = parametric_shapes(pulse_data.__class__).name
            except ValueError:
                pulse_type = pulse_data.__class__.__name__

            # get pulse name
            if pulse_data.name:
                pulse_name = pulse_data.name
            else:
                pulse_name = 'pulse:{pulse_id:d}'.format(pulse_id=hash(pulse_data))

            # get qubit index
            if sched_component.channel.name in channel_qubit_map:
                qubits = tuple(channel_qubit_map[sched_component.channel.name])
            else:
                raise CalExpError('Qubits associated with channel {chname} is not defined.'
                                  ''.format(chname=sched_component.channel.name))

            for pname, pval in pulse_data.parameters.items():
                # check if parameter value is parameter object
                if isinstance(pval, circuit.ParameterExpression):
                    parameter_kwargs[pname] = pval
                    continue

                parameter_attributes = {
                    'qubits': qubits,
                    'channel': sched_component.channel.name,
                    'inst_name': pulse_name,
                    'pulse_type': pulse_type,
                    'stretch_factor': stretch_factor
                }
                # check if parameter is already defined
                parameter_id = str(hash(tuple(parameter_attributes.values()) + (pname, )))
                if parameter_id in parameter_library:
                    parameter_kwargs[pname] = parameter_library[parameter_id]
                    continue

                # save parameter value in pulse table
                if pname == 'amp':
                    entries = dict(zip(('amp', 'phase'), (np.abs(pval), np.angle(pval))))
                else:
                    entries = {pname: pval}
                for _pname, _pval in entries.items():
                    pulse_table.set_parameter(name=_pname, cal_data=_pval, **parameter_attributes)

                # update pulse parameter and parameter library
                if pname in ['duration', 'width']:
                    # TODO support parametrization of duration and width.
                    new_parameter = pval
                else:
                    new_parameter = circuit.Parameter(pname)

                parameter_kwargs[pname] = new_parameter
                parameter_library[parameter_id] = new_parameter

            # overwrite schedule component
            sched_component = pulse.Play(type(pulse_data)(**parameter_kwargs, name=pulse_name),
                                         channel=sched_component.channel)

        # add new component
        template_sched.insert(t0, sched_component, inplace=True)

    return template_sched


def parse_backend_instmap(
        channel_qubit_map: Dict[str, Tuple[int]],
        instmap: pulse.InstructionScheduleMap,
        parameter_library: Dict[str, circuit.Parameter],
        parametric_shapes: Optional[Enum] = None) -> Tuple[PulseTable, ScheduleTemplate]:
    """Parse backend instruction schedule map and initialize :py:class:`PulseTable` and
    pt:class:`ScheduleTemplate`. Stretch factor is default to 1.0.

    Args:
        channel_qubit_map: A map between pulse channel string and qubit index.
        instmap: Instruction schedule map object that have backend calibrated gates.
        parameter_library: Collection of previously defined parameters.
        parametric_shapes: Enum objet that maps pulse name and ParametricPulse.

    Returns:
        Database of parameter table and schedule template.
    """
    pulse_table = PulseTable()
    sched_template = ScheduleTemplate()

    for inst_name, qubit_table in instmap._map.items():
        for qinds, sched in qubit_table.items():
            # create parametrized schedule
            temp_sched = decompose_schedule(
                channel_qubit_map=channel_qubit_map,
                gate_sched=sched,
                pulse_table=pulse_table,
                parameter_library=parameter_library,
                stretch_factor=1.0,
                parametric_shapes=parametric_shapes
            )
            sched_template.set_template_schedule(qinds, inst_name, temp_sched)

    return pulse_table, sched_template


def add_scope(name: str, channel: str, gate: str) -> str:
    """Add scope to parameter name.

    Args:
        name: Name of parameter.
        channel: Name of channel that the pulse associated with the parameter belongs to.
        gate: Name of gate that the pulse associated with the parameter composes.

    Returns:
          Name of parameter in local scope.
    """
    return '{}.{}.{}'.format(gate, channel, name)
