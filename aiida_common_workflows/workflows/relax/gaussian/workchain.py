# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Gaussian."""
import numpy as np
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import GaussianRelaxInputsGenerator

__all__ = ('GaussianRelaxWorkChain',)

GaussianBaseWorkChain = WorkflowFactory('gaussian.base')


@calcfunction
def get_total_energy(parameters):
    """Return the total energy from the output parameters node."""
    return orm.Float(parameters['scfenergies'][-1])  # already eV


@calcfunction
def get_forces(parameters):
    """Return the forces array from the output parameters node."""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=np.array(parameters['grads'][-1]))
    return forces


class GaussianRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Gaussian."""

    _process_class = GaussianBaseWorkChain
    _generator_class = GaussianRelaxInputsGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))
        self.out('forces', get_forces(self.ctx.workchain.outputs.output_parameters))
