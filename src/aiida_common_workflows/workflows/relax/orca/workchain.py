"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Orca."""
import numpy as np
from aiida.engine import calcfunction
from aiida.orm import ArrayData, Float
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import OrcaCommonRelaxInputGenerator

__all__ = ('OrcaCommonRelaxWorkChain',)

OrcaBaseWorkChain = WorkflowFactory('orca.base')

EV_TO_EH = 0.03674930814
ANG_TO_BOHR = 1.88972687


@calcfunction
def get_total_energy(parameters):
    """Return the total energy [eV] from the output parameters node."""
    return Float(parameters['scfenergies'][-1])  # already eV


@calcfunction
def get_forces(parameters):
    """Return the forces array [eV/ang] from the output parameters node."""
    # cclib parser keeps forces in au
    forces_au = np.array(parameters['grads'][-1])
    forces_arr = ArrayData()
    forces_arr.set_array(name='forces', array=forces_au * ANG_TO_BOHR / EV_TO_EH)
    return forces_arr


@calcfunction
def get_total_magnetization(parameters):
    """Return the total magnetizaton [Bohr magnetons] from the output parameters node."""
    # This is fully determined by the input multiplicity.
    # Find it from the mulliken atomic spins
    mulliken_spins = np.array(parameters['atomspins']['mulliken'])
    tot_magnetization = np.sum(mulliken_spins)
    return Float(tot_magnetization)


class OrcaCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Orca."""

    _process_class = OrcaBaseWorkChain
    _generator_class = OrcaCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        if 'relaxed_structure' in self.ctx.workchain.outputs:
            self.out('relaxed_structure', self.ctx.workchain.outputs.relaxed_structure)
        self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))
        if 'grads' in self.ctx.workchain.outputs.output_parameters.get_dict():
            self.out('forces', get_forces(self.ctx.workchain.outputs.output_parameters))
        if 'atomspins' in dict(self.ctx.workchain.outputs.output_parameters):
            self.out('total_magnetization', get_total_magnetization(self.ctx.workchain.outputs.output_parameters))


# EOF
