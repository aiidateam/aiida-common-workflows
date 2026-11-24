"""
Implementation of `aiida_common_workflows.common.pp.workchain.CommonPostProcessWorkChain` for Quantum ESPRESSO.
"""

from aiida.plugins import WorkflowFactory

from ..workchain import CommonPostProcessWorkChain
from .generator import QuantumEspressoCommonPostProcessInputGenerator

__all__ = ('QuantumEspressoCommonPostProcessWorkChain',)


class QuantumEspressoCommonPostProcessWorkChain(CommonPostProcessWorkChain):
    """
    Implementation of `aiida_common_workflows.common.pp.workchain.CommonPostProcessWorkChain` for Quantum ESPRESSO.
    """

    _process_class = WorkflowFactory('quantumespresso.pp.base')
    _generator_class = QuantumEspressoCommonPostProcessInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs
        self.out('quantity', outputs.output_data)
        self.out('remote_folder', outputs.remote_folder)
