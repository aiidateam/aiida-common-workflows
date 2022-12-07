# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Fleur."""
from aiida.orm import Float
from aiida.plugins import WorkflowFactory

from ..workchain import CommonBandsWorkChain
from .generator import FleurCommonBandsInputGenerator

__all__ = ('FleurCommonBandsWorkChain',)


class FleurCommonBandsWorkChain(CommonBandsWorkChain):
    """Implementation of `aiida_common_workflows.common.bands.workchain.CommonBandsWorkChain` for Fleur."""

    _process_class = WorkflowFactory('fleur.banddos')
    _generator_class = FleurCommonBandsInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.report('Bands calculation concluded sucessfully, converting outputs')
        if 'output_banddos_wc_bands' not in self.ctx.workchain.outputs:
            self.report('FleurBandDOSWorkChain concluded without returning bands!')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        #The bands output of fleur is shifted to have the fermi energy at zero
        self.out('fermi_energy', Float(0.0))

        self.out('bands', self.ctx.workchain.outputs['output_banddos_wc_bands'])
