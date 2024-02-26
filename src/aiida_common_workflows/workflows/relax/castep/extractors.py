"""
Collects some functions to postprocess a `CastepCommonRelaxWorkChain`.
"""
from aiida.common import LinkType
from aiida.orm import WorkChainNode
from aiida.plugins import WorkflowFactory

CastepCommonRelaxWorkChain = WorkflowFactory('common_workflows.relax.castep')


def get_ts_energy(common_relax_workchain):
    """
    Return the TS value of a concluded CastepCommonRelaxWorkChain.

    CASTEP reports three quantities related to the energy:

      - "free energy": ``Final free energy`` -  the total energy minus the TS term.
        This is the energy that gets minimised and is consistent with the forces calculated.
      - "total energy": ``Final energy`` - the total Khon-Sham energy.
      - "extrapolated 0K energy": ``NB est. 0K energy`` - the result of E-0.5TS to give better convergence.
      - "enthalpy": Is the free energy minus to PV term under finite temperature (for geometry optimisation).

    The TS term can extrapolated by subtracting the free energy from the total energy.
    """
    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != CastepCommonRelaxWorkChain:
        return ValueError('The input workchain is not a `CastepCommonRelaxWorkChain`')

    castep_base_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    e_ks = castep_base_wc.outputs.output_parameters['total energy']
    free_e = castep_base_wc.outputs.output_parameters['free energy']

    ts = e_ks - free_e

    return ts
