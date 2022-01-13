# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for CASTEP."""
from aiida.engine import calcfunction
from aiida.orm import Float
from aiida.plugins import WorkflowFactory

from ..workchain import CommonBandsWorkChain
from .generator import CastepCommonBandsInputGenerator

from logging import getLogger
logger = getLogger(__name__)

__all__ = ('CastepCommonBandsWorkChain',)


@calcfunction
def get_fermi_energy(bands):
    """Extract the Fermi energy from the BandsData output"""
    efermi = bands.get_attribute("efermi")
    if isinstance(efermi, list):
        efermi = efermi[0]
        logger.warn("Spin polarised calculation - using the efermi energy of the first spin channel.")
    return Float(efermi)


class CastepCommonBandsWorkChain(CommonBandsWorkChain):
    """Implementation of `aiida_common_workflows.common.bands.workchain.CommonBandsWorkChain` for SIESTA."""

    _process_class = WorkflowFactory('castep.bands')
    _generator_class = CastepCommonBandsInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        if 'band_structure' not in self.ctx.workchain.outputs:
            self.report('CastepBandsWorkChain concluded without returning bands!')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        self.out('fermi_energy', get_fermi_energy(self.ctx.workchain.outputs['band_structure']))

        self.out('bands', self.ctx.workchain.outputs['band_structure'])
