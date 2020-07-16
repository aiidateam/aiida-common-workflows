# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CP2K."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain

__all__ = ('Cp2kRelaxWorkChain',)

Cp2kRelaxWorkChain = WorkflowFactory('cp2k.base')

@calcfunction
def get_total_energy(parameters):
    """Return the total energy from the given parameters node."""
    return orm.Float(parameters.get_attribute('energy'))

@calcfunction
def get_forces_output_folder(folder):
    """Return the forces array from the given trajectory data."""
    forces = orm.ArrayData()
    return forces


class Cp2kRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CP2K."""

    _process_class = Cp2kRelaxWorkChain

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))
