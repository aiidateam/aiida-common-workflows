"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for GPAW."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import GpawCommonRelaxInputGenerator

__all__ = ('GpawCommonRelaxWorkChain',)


@calcfunction
def extract_forces_from_array(array):
    """Return the forces and stress arrays from the given trajectory data."""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=array.get_array('forces'))
    return forces


@calcfunction
def extract_total_energy_from_parameters(parameters):
    """Return the total energy from the given parameters node."""
    energy_cont = parameters.base.attributes.get('energy_contributions')
    total_energy = energy_cont['xc'] + energy_cont['local'] + energy_cont['kinetic']
    total_energy += energy_cont['external'] + energy_cont['potential'] + energy_cont['entropy (-st)']
    return orm.Float(total_energy)


class GpawCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for GPAW."""

    _process_class = WorkflowFactory('ase.gpaw.base')
    _generator_class = GpawCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        total_energy = extract_total_energy_from_parameters(outputs.parameters)
        forces = extract_total_energy_from_parameters(outputs.array)

        if 'output_structure' in outputs:
            self.out('relaxed_structure', outputs.output_structure)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
