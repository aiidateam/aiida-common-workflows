# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import VaspRelaxInputsGenerator

__all__ = ('VaspRelaxWorkChain',)


@calcfunction
def get_stress(stress):
    """Return the final stress array."""
    stress_data = orm.ArrayData()
    stress_data.set_array(name='stress', array=stress.get_array('final'))
    return stress_data


@calcfunction
def get_forces(forces):
    """Return the final forces array.."""
    forces_data = orm.ArrayData()
    forces_data.set_array(name='forces', array=forces.get_array('final'))
    return forces_data


@calcfunction
def get_total_energy(misc):
    """Return the total energy from misc."""
    misc_dict = misc.get_dict()
    total_energy = orm.Float(misc_dict['total_energies']['energy_no_entropy'])
    return total_energy


class VaspRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""

    _process_class = WorkflowFactory('vasp.relax')
    _generator_class = VaspRelaxInputsGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.relax__structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.misc))
        self.out('forces', get_forces(self.ctx.workchain.outputs.forces))
        self.out('stress', get_stress(self.ctx.workchain.outputs.stress))
