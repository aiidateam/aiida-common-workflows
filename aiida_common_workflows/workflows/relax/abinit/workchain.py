# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Abinit."""
import numpy as np

from aiida import orm
from aiida.engine import calcfunction
from aiida.common import exceptions
from aiida_abinit.workflows.base import AbinitBaseWorkChain

from ..workchain import CommonRelaxWorkChain
from .generator import AbinitRelaxInputsGenerator

__all__ = ('AbinitRelaxWorkChain',)


@calcfunction
def get_stress(parameters):
    """Return the stress array from the given parameters node."""
    stress = orm.ArrayData()
    stress.set_array(name='stress', array=np.array(parameters.get_attribute('cart_stress_tensor')))
    return stress


@calcfunction
def get_forces(parameters):
    """Return the forces array from the given parameters node."""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=np.array(parameters.get_attribute('forces')))
    return forces


@calcfunction
def get_total_energy(parameters):
    """Return the total energy from the given parameters node."""
    return orm.Float(parameters.get_attribute('energy'))


@calcfunction
def get_total_magnetization(parameters):
    """Return the total magnetization from the given parameters node."""
    return orm.Float(parameters['total_magnetization'])


class AbinitRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Abinit."""

    _process_class = AbinitBaseWorkChain
    _generator_class = AbinitRelaxInputsGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        try:
            self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        except exceptions.NotExistentAttributeError:
            pass
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))
        self.out('forces', get_forces(self.ctx.workchain.outputs.output_parameters))
        self.out('stress', get_stress(self.ctx.workchain.outputs.output_parameters))
        try:
            self.out('total_magnetization', get_total_magnetization(self.ctx.workchain.outputs.output_parameters))
        except KeyError:
            pass
