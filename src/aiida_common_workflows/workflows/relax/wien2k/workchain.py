"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Wien2k."""
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import Wien2kCommonRelaxInputGenerator

__all__ = ('Wien2kCommonRelaxWorkChain',)


@calcfunction
def get_energy(pardict):
    """Extract the energy from the `workchain_result` dictionary (Ry -> eV)"""
    return orm.Float(pardict['EtotRyd'] * 13.605693122994)


class Wien2kCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for WIEN2k."""

    _process_class = WorkflowFactory('wien2k.scf123_wf')
    _generator_class = Wien2kCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        self.report('Relaxation task concluded sucessfully, converting outputs')
        self.out('total_energy', get_energy(self.ctx.workchain.outputs.workchain_result))
        self.out('relaxed_structure', self.ctx.workchain.outputs.aiida_structure_out)
