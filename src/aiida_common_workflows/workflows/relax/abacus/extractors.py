"""
Post-processing extractor functions for the ``QuantumEspressoCommonRelaxWorkChain``.
"""

from aiida.common import LinkType
from aiida.orm import WorkChainNode

from .workchain import AbacusCommonRelaxWorkChain


def get_ts_energy(common_relax_workchain: AbacusCommonRelaxWorkChain) -> float:
    """Return the T * S value of a concluded ``QuantumEspressoCommonRelaxWorkChain``.

    Here, T is the fictitious temperature due to the use of smearing and S is the entropy. This "smearing contribution"
    to the free energy in Abacus  is expressed as -T * S:

        E_KS(sigma->0)

    This energy is printed at every electronic cycle.
    :param common_relax_workchain: ``AbacusCommonRelaxWorkChain`` for which to extract the smearing energy.
    :returns: The T*S value in eV.
    """
    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != AbacusCommonRelaxWorkChain:
        return ValueError('The input workchain is not a `AbacusCommonRelaxWorkChain`')

    abacus_relax_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    return abacus_relax_wc.outputs.misc['ts_contribution']
