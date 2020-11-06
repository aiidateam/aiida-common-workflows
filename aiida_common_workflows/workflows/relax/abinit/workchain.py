# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Abinit."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.common import exceptions
from aiida_abinit.workflows.base import AbinitBaseWorkChain

from ..workchain import CommonRelaxWorkChain
from .generator import AbinitRelaxInputsGenerator

__all__ = ('AbinitRelaxWorkChain',)


@calcfunction
def get_stress_from_trajectory(trajectory):
    """Return the stress array from the given trajectory data."""
    stress = orm.ArrayData()
    stress.set_array(name='stress', array=trajectory.get_array('stress')[-1])
    return stress


@calcfunction
def get_forces_from_trajectory(trajectory):
    """Return the forces array from the given trajectory data."""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=trajectory.get_array('forces')[-1])
    return forces


@calcfunction
def get_total_energy(parameters):
    """Return the total energy from the given parameters node."""
    return orm.Float(parameters.get_attribute('energy'))


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
        self.out('forces', get_forces_from_trajectory(self.ctx.workchain.outputs.output_trajectory))
        self.out('stress', get_stress_from_trajectory(self.ctx.workchain.outputs.output_trajectory))
