# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for GPAW."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import GPAWCommonRelaxInputGenerator

__all__ = ('GPAWCommonRelaxWorkChain',)


@calcfunction
def extract_from_array(array):
    """Return the forces and stress arrays from the given trajectory data."""
    forces = orm.ArrayData()
    forces.set_array(name='forces', array=array.get_array('forces'))

    return {'forces': forces}


@calcfunction
def extract_from_parameters(parameters):
    """Return the total energy from the given parameters node."""
    total_energy = parameters.get_attribute('energy')
    results = {'total_energy': orm.Float(total_energy)}

    return results


class GPAWCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for GPAW."""

    _process_class = WorkflowFactory('ase.gpaw.base')
    _generator_class = GPAWCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        total_energy, = extract_from_parameters(outputs.parameters).values()
        forces, = extract_from_array(outputs.array).values()

        if 'output_structure' in outputs:
            self.out('relaxed_structure', outputs.output_structure)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
