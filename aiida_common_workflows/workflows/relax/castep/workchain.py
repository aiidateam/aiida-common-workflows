# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CASTEP"""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import CastepRelaxInputGenerator

__all__ = ('CastepRelaxWorkChain',)


@calcfunction
def get_stress_from_trajectory(trajectory):
    """Return the stress array from the given trajectory data."""
    stress = orm.ArrayData()

    arraynames = trajectory.get_arraynames()
    # Raw stress takes the precedence here
    if "stress" in arraynames:
        array_ = trajectory.get_array('stress')
    else:
        array_ = trajectory.get_array('symm_stress')
    stress.set_array(name='stress', array=array_[-1])
    return stress


@calcfunction
def get_forces_from_trajectory(trajectory):
    """Return the forces array from the given trajectory data."""
    forces = orm.ArrayData()
    arraynames = trajectory.get_arraynames()
    # Raw forces takes the precedence here
    if "forces" in arraynames:
        array_ = trajectory.get_array('forces')
    else:
        array_ = trajectory.get_array('cons_forces')

    forces.set_array(name='forces', array=array_[-1])
    return forces


@calcfunction
def get_free_energy(parameters):
    """
    Return the free energy from the given parameters node.
    The free energy reported by CASTEP is the one that is consistent with the forces.
    """
    return orm.Float(parameters.get_attribute('free_energy'))


class CastepRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CASTEP"""

    _process_class = WorkflowFactory('castep.relax')
    _generator_class = CastepRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_free_energy(self.ctx.workchain.outputs.output_parameters))
        self.out('forces', get_forces_from_trajectory(self.ctx.workchain.outputs.output_trajectory))
        self.out('stress', get_stress_from_trajectory(self.ctx.workchain.outputs.output_trajectory))
