"""
Collects some functions to postprocess a `VaspCommonRelaxWorkChain`.
"""


def get_ts_energy(common_relax_workchain):
    """
    Extract and return the energy contribution from the entropy term TS value.

    The fictitious temperature is T due to the presence of a smearing and S is the entropy.
    """
    from aiida.common import LinkType
    from aiida.orm import WorkChainNode
    from aiida.plugins import WorkflowFactory

    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != WorkflowFactory('common_workflows.relax.vasp'):
        return ValueError('The input workchain is not a `VaspCommonRelaxWorkChain`')

    vasp_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    energies = vasp_wc.outputs.energies
    energy_free = energies.get_array('energy_free_electronic')[0]
    energy_no_entropy = energies.get_array('energy_no_entropy')[0]
    energy_entropy_contrib = energy_no_entropy - energy_free

    return energy_entropy_contrib
