# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for SIESTA."""
from aiida.plugins import WorkflowFactory

from ..workchain import CommonBandsWorkChain
from .generator import SiestaCommonBandsInputGenerator

__all__ = ('SiestaCommonBandsWorkChain',)


class SiestaCommonBandsWorkChain(CommonBandsWorkChain):
    """Implementation of `aiida_common_workflows.common.bands.workchain.CommonBandsWorkChain` for SIESTA."""

    _process_class = WorkflowFactory('siesta.base')
    _generator_class = SiestaCommonBandsInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        if 'bands' not in self.ctx.workchain.outputs:
            self.report('SiestaBaseWorkChain concluded without returning bands!')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED
        self.out('bands', self.ctx.workchain.outputs['bands'])
