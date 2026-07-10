"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""
import numpy as np
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import AbacusCommonRelaxInputGenerator

__all__ = ('AbacusCommonRelaxInputGenerator',)


@calcfunction
def extract_from_misc(misc):
    """Return the total energy and optionally the total magnetization from the given parameters node."""

    # Default to use the free energy (E_KohnSham - TS) since it is consistent with the
    # forces and is also used by the ACWF verification project
    total_energy = misc.base.attributes.get('total_energy')
    total_magnetization = misc.base.attributes.get('total_magnetization', None)

    results = {'total_energy': orm.Float(total_energy)}  # The reported energy is eV

    # Get the forces and stress, abacus report these values in eV/A and KBar
    forces = np.array(misc['final_forces'])
    forces = orm.ArrayData({'forces': forces})
    stress = np.array(misc['final_stress']) / 10  # Convert to GPa
    stress = orm.ArrayData({'stress': stress})

    if total_magnetization is not None:
        results['total_magnetization'] = orm.Float(total_magnetization)

    return {'total_energy': orm.Float(total_energy), 'forces': forces, 'stress': stress}


class AbacusCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""

    _process_class = WorkflowFactory('abacus.relax')
    _generator_class = AbacusCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        res = extract_from_misc(outputs.misc)
        forces = res['forces']
        stress = res['stress']
        total_energy = res['total_energy']

        if 'structure' in outputs:
            self.out('relaxed_structure', outputs.structure)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
        self.out('stress', stress)
