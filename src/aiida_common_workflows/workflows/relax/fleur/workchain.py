"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for FLEUR (www.flapw.de)."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import FleurCommonRelaxInputGenerator

__all__ = ('FleurCommonRelaxWorkChain',)


@calcfunction
def get_forces_from_trajectory(trajectory):
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
    return orm.Float(parameters.base.attributes.get('energy'))


@calcfunction
def get_total_magnetization(parameters):
    """Return the total magnetic moment of the cell from the given parameters node."""
    return orm.Float(parameters.base.attributes.get('total_magnetic_moment_cell'))


class FleurCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for FLEUR."""

    _process_class = WorkflowFactory('fleur.base_relax')
    _generator_class = FleurCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""

        outputs = self.ctx.workchain.outputs

        if 'optimized_structure' in outputs:
            self.out('relaxed_structure', outputs.optimized_structure)

        if 'last_scf' in outputs:
            self.out('remote_folder', outputs.last_scf.last_calc.remote_folder)

        output_parameters = outputs.output_relax_wc_para
        out_para_dict = output_parameters.get_dict()
        if 'total_magnetic_moment_cell' in out_para_dict:
            if out_para_dict.get('total_magnetic_moment_cell', None) is not None:
                self.out('total_magnetization', get_total_magnetization(output_parameters))
        self.out('total_energy', get_total_energy(outputs.output_relax_wc_para))
        self.out('forces', get_forces_from_trajectory(outputs.output_relax_wc_para))
