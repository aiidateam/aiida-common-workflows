# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory, DataFactory

from ..workchain import CommonRelaxWorkChain

__all__ = ('CommonVASPRelaxWorkChain',)

VASPRelaxWorkChain = WorkflowFactory('vasp.relax')  # pylint: disable=invalid-name


@calcfunction
def get_stress(stress):
    """Return the final stress array."""
    stress_data = DataFactory('array')()
    stress_data.set_array(name='stress', array=stress.get_array('final'))
    return stress_data


@calcfunction
def get_forces(forces):
    """Return the final forces array.."""
    forces_data = DataFactory('array')()
    forces_data.set_array(name='forces', array=forces.get_array('final'))
    return forces_data


@calcfunction
def get_total_energy(misc):
    """Return the total energy from misc."""
    misc_dict = misc.get_dict()
    total_energy = DataFactory('float')(misc_dict['total_energies']['energy_no_entropy'])
    return total_energy


class CommonVASPRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""

    _process_class = VASPRelaxWorkChain

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.relax__structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.misc))
        self.out('forces', get_forces(self.ctx.workchain.outputs.forces))
        self.out('stress', get_stress(self.ctx.workchain.outputs.stress))
