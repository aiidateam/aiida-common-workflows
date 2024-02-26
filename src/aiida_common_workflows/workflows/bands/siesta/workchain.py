"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""
from aiida.engine import calcfunction
from aiida.orm import Float
from aiida.plugins import WorkflowFactory

from ..workchain import CommonBandsWorkChain
from .generator import SiestaCommonBandsInputGenerator

__all__ = ('SiestaCommonBandsWorkChain',)


@calcfunction
def get_fermi_energy(pardict):
    """Extract the Fermi energy from the `output_parameters` dictionary"""
    return Float(pardict['E_Fermi'])


class SiestaCommonBandsWorkChain(CommonBandsWorkChain):
    """Implementation of `aiida_common_workflows.common.bands.workchain.CommonBandsWorkChain` for SIESTA."""

    _process_class = WorkflowFactory('siesta.base')
    _generator_class = SiestaCommonBandsInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        if 'bands' not in self.ctx.workchain.outputs:
            self.report('SiestaBaseWorkChain concluded without returning bands!')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        self.out('fermi_energy', get_fermi_energy(self.ctx.workchain.outputs.output_parameters))

        self.out('bands', self.ctx.workchain.outputs['bands'])
