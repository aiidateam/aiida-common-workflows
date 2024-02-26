"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import SiestaCommonRelaxInputGenerator

__all__ = ('SiestaCommonRelaxWorkChain',)


@calcfunction
def get_energy(pardict):
    """
    Extract the energy from the `output_parameters` dictionary.

    The energy to use is the Free energy since a fictitious electronic temperature
    have been introduced in the calculations.
    """
    return orm.Float(pardict['FreeE'])


@calcfunction
def get_magn(pardict):
    """Extract the energy from the `output_parameters` dictionary"""
    return orm.Float(pardict['stot'])


@calcfunction
def get_forces_and_stress(totalarray):
    """
    Separates the forces and stress in two different arrays and correct the units of stress.

    Stress in siesta plugin is return in units of Ry/Ang³. Here we want them in eV/Ang³
    """
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=totalarray.get_array('forces'))
    stress = orm.ArrayData()
    stress_correct_units = totalarray.get_array('stress') * 13.6056980659
    stress.set_array(name='stress', array=stress_correct_units)
    return {'forces': forces, 'stress': stress}


class SiestaCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""

    _process_class = WorkflowFactory('siesta.base')
    _generator_class = SiestaCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.report('Relaxation task concluded sucessfully, converting outputs')
        if 'output_structure' in self.ctx.workchain.outputs:
            self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_energy(self.ctx.workchain.outputs.output_parameters))
        res_dict = get_forces_and_stress(self.ctx.workchain.outputs.forces_and_stress)
        self.out('forces', res_dict['forces'])
        self.out('stress', res_dict['stress'])
        if 'stot' in self.ctx.workchain.outputs.output_parameters.base.attributes.all:
            self.out('total_magnetization', get_magn(self.ctx.workchain.outputs.output_parameters))
        self.out('remote_folder', self.ctx.workchain.outputs.remote_folder)
