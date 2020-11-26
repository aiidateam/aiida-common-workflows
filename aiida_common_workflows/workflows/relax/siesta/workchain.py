# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import SiestaRelaxInputsGenerator

__all__ = ('SiestaRelaxWorkChain',)


@calcfunction
def get_energy(pardict):
    """Extract the energy from the `output_parameters` dictionary"""
    return orm.Float(pardict['E_KS'])


@calcfunction
def get_forces_and_stress(totalarray):
    """Separates the forces and stress in two different arrays"""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=totalarray.get_array('forces'))
    stress = orm.ArrayData()
    stress.set_array(name='stress', array=totalarray.get_array('stress'))
    return {'forces': forces, 'stress': stress}


class SiestaRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""

    _process_class = WorkflowFactory('siesta.base')
    _generator_class = SiestaRelaxInputsGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.report('Relaxation task concluded sucessfully, converting outputs')
        if 'output_structure' in self.ctx.workchain.outputs:
            self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_energy(self.ctx.workchain.outputs.output_parameters))
        res_dict = get_forces_and_stress(self.ctx.workchain.outputs.forces_and_stress)
        self.out('forces', res_dict['forces'])
        self.out('stress', res_dict['stress'])
