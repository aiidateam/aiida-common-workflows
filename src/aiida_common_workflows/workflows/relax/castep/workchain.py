"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CASTEP"""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import CastepCommonRelaxInputGenerator

__all__ = ('CastepCommonRelaxWorkChain',)


@calcfunction
def get_stress_from_trajectory(trajectory):
    """Return the stress array from the given trajectory data."""

    # Taken from http://greif.geo.berkeley.edu/~driver/conversions.html
    # 1 eV/Angstrom3 = 160.21766208 GPa
    ev_to_gpa = 160.21766208

    stress = orm.ArrayData()

    arraynames = trajectory.get_arraynames()
    # Raw stress takes the precedence here
    if 'stress' in arraynames:
        array_ = trajectory.get_array('stress')
    else:
        array_ = trajectory.get_array('symm_stress')
    # Convert stress back to eV/Angstrom3, CASTEP output in GPa
    stress.set_array(name='stress', array=array_[-1] / ev_to_gpa)
    return stress


@calcfunction
def get_forces_from_trajectory(trajectory):
    """Return the forces array from the given trajectory data."""
    forces = orm.ArrayData()
    arraynames = trajectory.get_arraynames()
    # Raw forces takes the precedence here
    # Forces are already in eV/Angstrom
    if 'forces' in arraynames:
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
    return orm.Float(parameters.base.attributes.get('free_energy'))


@calcfunction
def get_total_magnetization(parameters):
    """
    Return the free energy from the given parameters node.
    The free energy reported by CASTEP is the one that is consistent with the forces.
    """
    return orm.Float(parameters.base.attributes.get('spin_density'))


class CastepCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CASTEP"""

    _process_class = WorkflowFactory('castep.relax')
    _generator_class = CastepCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        workchain = self.ctx.workchain
        if 'output_structure' in workchain.outputs:
            self.out('relaxed_structure', workchain.outputs.output_structure)

        output_parameters = workchain.outputs.output_parameters
        self.out('total_energy', get_free_energy(output_parameters))

        if 'spin_density' in output_parameters.get_dict():
            self.out('total_magnetization', get_total_magnetization(output_parameters))

        if 'output_trajectory' in workchain.outputs:
            self.out('forces', get_forces_from_trajectory(workchain.outputs.output_trajectory))
            self.out('stress', get_stress_from_trajectory(workchain.outputs.output_trajectory))
        # This can be a single point calculation - get force/stress from the ArrayData
        else:
            self.out('forces', get_forces_from_trajectory(workchain.outputs.output_array))
            self.out('stress', get_stress_from_trajectory(workchain.outputs.output_array))
