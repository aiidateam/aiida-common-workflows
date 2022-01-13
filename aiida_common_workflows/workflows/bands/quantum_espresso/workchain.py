# -*- coding: utf-8 -*-
"""Implementation of the ``CommonBandsWorkChain`` for Quantum ESPRESSO."""
from aiida.engine import calcfunction
from aiida.orm import Float
from aiida.plugins import WorkflowFactory

from ..workchain import CommonBandsWorkChain
from .generator import QuantumEspressoCommonBandsInputGenerator

__all__ = ('QuantumEspressoCommonBandsWorkChain',)


@calcfunction
def get_fermi_energy(output_parameters):
    """Extract the Fermi energy from the ``output_parameters`` of a ``PwBaseWorkChain``."""
    return Float(output_parameters['fermi_energy'])


class QuantumEspressoCommonBandsWorkChain(CommonBandsWorkChain):
    """Implementation of the ``CommonBandsWorkChain`` for Quantum ESPRESSO."""

    _process_class = WorkflowFactory('quantumespresso.pw.base')
    _generator_class = QuantumEspressoCommonBandsInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub work chain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        if 'output_band' not in outputs:
            self.report('The `bands` PwBaseWorkChain does not have the `output_band` output.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        self.out('bands', outputs.output_band)
        self.out('fermi_energy', get_fermi_energy(outputs.output_parameters))
