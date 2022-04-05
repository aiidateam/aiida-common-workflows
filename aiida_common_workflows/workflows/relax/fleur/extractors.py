# -*- coding: utf-8 -*-
"""
Collects some functions to postprocess a `FleurCommonRelaxWorkChain`.
"""


def get_ts_energy(common_relax_workchain):
    """
    Return the TS value of a concluded FleurCommonRelaxWorkChain.

    T the fictitious temperature due to the presence of a smearing and S is
    the entropy. The units must be eV.
    In Fleur this contribution is directly available in the output parameters
    of the Fleur calculation
    """
    from aiida.common import LinkType
    from aiida.orm import WorkChainNode
    from aiida.plugins import WorkflowFactory

    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != WorkflowFactory('common_workflows.relax.fleur'):
        return ValueError('The input workchain is not a `FleurCommonRelaxWorkChain`')

    fleur_relax_wc = common_relax_workchain.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    output_parameters = fleur_relax_wc.outputs.last_scf.last_calc.output_parameters

    ts = output_parameters['ts_energy']  #pylint: disable=invalid-name

    return ts
