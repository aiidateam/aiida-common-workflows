# -*- coding: utf-8 -*-
"""
Collects some functions to postprocess a `CommonWorkflowSiestaWorkChain`.
"""


def get_ts_energy(common_relax_workchain):
    """
    Return the TS value of a concluded CommonWorkflowAbinitWorkChain.
    T the fictitious temperature due to the presence of a smearing and S is
    the entropy. The units must be eV.
    """
    from aiida.common import LinkType
    from aiida.orm import WorkChainNode
    from aiida.plugins import WorkflowFactory

    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != WorkflowFactory('common_workflows.relax.abinit'):
        return ValueError('The input workchain is not a `CommonWorkflowAbinitWorkChain`')

    abinit_base_wc = common_relax_workchain.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    e_entropy = abinit_base_wc.outputs.output_parameters['e_entropy']  # eV

    return e_entropy
