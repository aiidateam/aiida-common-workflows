"""
Collects some functions to postprocess a `CommonWorkflowAbinitWorkChain`.
"""

from aiida.common import LinkType
from aiida.orm import WorkChainNode

from .workchain import AbinitCommonRelaxWorkChain


def get_ts_energy(common_relax_workchain: AbinitCommonRelaxWorkChain) -> float:
    """
    Return the TS value of a concluded AbinitCommonRelaxWorkChain.
    T the fictitious temperature due to the presence of a smearing and S is
    the entropy. The units must be eV.
    In Abinit, the term `-TS` is output as `e_entropy` with units of eV.

    :param common_relax_workchain: ``AbinitCommonRelaxWorkChain`` for which to extract the smearing energy.
    :returns: The T*S value in eV.
    """
    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != AbinitCommonRelaxWorkChain:
        return ValueError('The input workchain is not a `AbinitCommonRelaxWorkChain`')

    abinit_base_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    return -abinit_base_wc.outputs.output_parameters['e_entropy']
