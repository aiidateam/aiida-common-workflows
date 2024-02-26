"""
Post-processing extractor functions for the ``QuantumEspressoCommonRelaxWorkChain``.
"""

from aiida.common import LinkType
from aiida.orm import WorkChainNode

from .workchain import QuantumEspressoCommonRelaxWorkChain


def get_ts_energy(common_relax_workchain: QuantumEspressoCommonRelaxWorkChain) -> float:
    """Return the T * S value of a concluded ``QuantumEspressoCommonRelaxWorkChain``.

    Here, T is the fictitious temperature due to the use of smearing and S is the entropy. This "smearing contribution"
    to the free energy in Quantum ESPRESSO is expressed as -T * S:

        smearing contrib. (-TS)   =      -0.00153866 Ry

    And the ``PwParser`` also maintains this sign, i.e. it only converts the units to eV.

    :param common_relax_workchain: ``QuantumEspressoCommonRelaxWorkChain`` for which to extract the smearing energy.
    :returns: The T*S value in eV.
    """
    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != QuantumEspressoCommonRelaxWorkChain:
        return ValueError('The input workchain is not a `QuantumEspressoCommonRelaxWorkChain`')

    qe_relax_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    return -qe_relax_wc.outputs.output_parameters['energy_smearing']
