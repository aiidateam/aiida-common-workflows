# -*- coding: utf-8 -*-
"""
Collects some functions to postprocess a `CommonWorkflowSiestaWorkChain`.
"""


def return_ts(common_relax_workchain):
    """
    Return the TS value of a concluded CommonWorkflowSiestaWorkChain.

    In siesta this quantity is not reported in the output parameters, but can be
    extracted from FreeE = E_KS - TS
    """
    from aiida.common import LinkType
    from aiida.orm import WorkChainNode
    from aiida.plugins import WorkflowFactory

    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != WorkflowFactory('common_workflows.relax.siesta'):
        return ValueError('The input workchain is not a `CommonWorkflowSiestaWorkChain`')

    siesta_base_wc = common_relax_workchain.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    e_ks = siesta_base_wc.outputs.output_parameters['E_KS']
    free_e = siesta_base_wc.outputs.output_parameters['FreeE']

    ts = e_ks - free_e  #pylint: disable=invalid-name

    return ts
