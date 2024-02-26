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
    from masci_tools.io.io_fleurxml import load_outxml
    from masci_tools.util.constants import HTR_TO_EV
    from masci_tools.util.schema_dict_util import evaluate_attribute

    if not isinstance(common_relax_workchain, WorkChainNode):
        return ValueError('The input is not a workchain (instance of `WorkChainNode`)')
    if common_relax_workchain.process_class != WorkflowFactory('common_workflows.relax.fleur'):
        return ValueError('The input workchain is not a `FleurCommonRelaxWorkChain`')

    fleur_relax_wc = common_relax_workchain.base.links.get_outgoing(link_type=LinkType.CALL_WORK).one().node
    fleur_calc_out = fleur_relax_wc.outputs.last_scf.last_calc

    output_parameters = fleur_calc_out.output_parameters
    ts = None
    if 'ts_energy' in output_parameters.keys():
        ts = output_parameters['ts_energy']
    elif fleur_relax_wc.is_finished_ok:
        # This check makes sure that the parsing worked before so we don't get
        # nasty surprises in load_outxml

        with fleur_calc_out.retrieved.open('out.xml', 'rb') as file:
            xmltree, schema_dict = load_outxml(file)
        try:
            ts_all = evaluate_attribute(
                xmltree, schema_dict, 'value', tag_name='tkbtimesentropy', iteration_path=True, list_return=True
            )
        except ValueError:
            pass
        else:
            if ts_all:
                ts = ts_all[-1] * HTR_TO_EV

    return ts
