"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for pyscf."""
import numpy
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import PyscfCommonRelaxInputGenerator

__all__ = ('PyscfCommonRelaxWorkChain',)


@calcfunction
def extract_energy_from_parameters(parameters):
    """Return the total energy from the given parameters node."""
    total_energy = parameters.get_attribute('total_energy')
    return {'total_energy': orm.Float(total_energy)}


@calcfunction
def extract_forces_from_parameters(parameters):
    """Return the forces from the given parameters node."""
    forces = orm.ArrayData()
    forces.set_array('forces', numpy.array(parameters.get_attribute('forces')))
    return {'forces': forces}


class PyscfCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for pyscf."""

    _process_class = WorkflowFactory('pyscf.base')
    _generator_class = PyscfCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs
        total_energy = extract_energy_from_parameters(outputs.parameters)['total_energy']
        forces = extract_forces_from_parameters(outputs.parameters)['forces']

        if 'structure' in outputs:
            self.out('relaxed_structure', outputs.structure)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
