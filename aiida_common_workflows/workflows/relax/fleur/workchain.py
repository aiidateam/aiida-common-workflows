# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain

__all__ = ('FleurRelaxWorkChain',)

AiidaFleurRelaxWorkChain = WorkflowFactory('fleur.base_relax')#fleur.relax')
#AiidaFleurRelaxWorkChain = WorkflowFactory('fleur.relax')

@calcfunction
def get_stress_from_trajectory(trajectory):
    stress = orm.ArrayData()
    # stress.set_array(name='stress', array=trajectory.get_array('stress')[-1])
    # FLeur does not have stress
    return stress


@calcfunction
def get_forces_from_trajectory(trajectory):
    forces = orm.ArrayData()
    # currently the fleur relax workchain does not output trajectory data, but it will be adapted to do so
    #forces.set_array(name='forces', array=trajectory.get_array('forces')[-1])
    return forces


@calcfunction
def get_total_energy(parameters):

    return orm.Float('123')#parameters.get_attribute('energy'))


class FleurRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for FLEUR."""

    _process_class = AiidaFleurRelaxWorkChain

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.optimized_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.out))
        self.out('forces', get_forces_from_trajectory(self.ctx.workchain.outputs.out))#put_trajectory))
        self.out('stress', get_stress_from_trajectory(self.ctx.workchain.outputs.out))#put_trajectory
