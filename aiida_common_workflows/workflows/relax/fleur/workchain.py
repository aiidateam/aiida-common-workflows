# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for FLEUR (www.flapw.de)."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import FleurRelaxInputsGenerator

__all__ = ('FleurRelaxWorkChain',)


@calcfunction
def get_forces_from_trajectory(trajectory):  # pylint: disable=unused-argument
    """Calcfunction to get forces from trajectory"""
    forces = orm.ArrayData()
    # currently the fleur relax workchain does not output trajectory data,
    # but it will be adapted to do so
    # largest forces are found in workchain output nodes
    # forces.set_array(name='forces', array=trajectory.get_array('forces')[-1])
    return forces


@calcfunction
def get_total_energy(parameters):
    """Calcfunction to get total energy from relax output"""
    return orm.Float(parameters.get_attribute('energy'))


class FleurRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for FLEUR."""

    _process_class = WorkflowFactory('fleur.base_relax')
    _generator_class = FleurRelaxInputsGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.optimized_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.out))
        self.out('forces', get_forces_from_trajectory(self.ctx.workchain.outputs.out))
