# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CP2K."""
import numpy as np
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain

__all__ = ('Cp2kRelaxWorkChain',)

Cp2kBaseWorkChain = WorkflowFactory('cp2k.base')

EV_A3_TO_BAR = 1602176.6208
HA_BOHR_TO_EV_A = 51.42208619083232
HA_TO_EV = 27.211396


@calcfunction
def get_total_energy(parameters):
    """Return the total energy from the given parameters node."""
    return orm.Float(parameters.get_attribute('energy') * HA_TO_EV)


@calcfunction
def get_forces_output_folder(folder):
    """Return the forces array from the retrieved output files."""
    string_content = folder.get_object_content('aiida-frc-1.xyz')
    lines = string_content.splitlines()
    natoms = int(lines[0])
    forces_array = np.empty((natoms, 3))
    for i, line in enumerate(lines[-natoms:]):
        forces_array[i] = [float(s) for s in line.split()[1:]]
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=forces_array * HA_BOHR_TO_EV_A)
    return forces


@calcfunction
def get_stress_output_folder(folder):
    """Return the stress array from the retrieved output files."""
    string = folder.get_object_content('aiida-1.stress')
    stress = orm.ArrayData()
    stress_array = np.array(string.splitlines()[-1].split()[2:], dtype=float) / EV_A3_TO_BAR
    stress.set_array(name='stress', array=stress_array.reshape(3, 3))
    return stress


class Cp2kRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CP2K."""

    _process_class = Cp2kBaseWorkChain

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))
        self.out('forces', get_forces_output_folder(self.ctx.workchain.outputs.retrieved))
        self.out('stress', get_stress_output_folder(self.ctx.workchain.outputs.retrieved))
