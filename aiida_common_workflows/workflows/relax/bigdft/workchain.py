# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT"""
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import BigDftRelaxInputGenerator

__all__ = ('BigDftRelaxWorkChain',)


class BigDftRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT."""

    _process_class = WorkflowFactory('bigdft.relax')
    _generator_class = BigDftRelaxInputGenerator

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.expose_outputs(cls._process_class)

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.out_many(self.exposed_outputs(self.ctx.workchain, self._process_class))
