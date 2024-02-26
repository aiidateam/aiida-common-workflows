"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT"""
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import BigDftCommonRelaxInputGenerator

__all__ = ('BigDftCommonRelaxWorkChain',)


class BigDftCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT."""

    _process_class = WorkflowFactory('bigdft')
    _generator_class = BigDftCommonRelaxInputGenerator

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.expose_outputs(cls._process_class)

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out_many(self.exposed_outputs(self.ctx.workchain, self._process_class))
