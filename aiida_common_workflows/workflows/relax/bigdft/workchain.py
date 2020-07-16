# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT"""
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain

__all__ = ('BigDFTCommonRelaxWorkChain',)

RelaxWorkChain = WorkflowFactory('bigdft.relax')


class BigDFTCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for BigDFT."""

    _process_class = RelaxWorkChain

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.expose_outputs(RelaxWorkChain)

    def convert_outputs(self):
        self.out_many(self.exposed_outputs(self.ctx.workchain, RelaxWorkChain))
