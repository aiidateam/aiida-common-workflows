"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Wien2k."""
import os

import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('Wien2kCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class Wien2kCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Generator of inputs for the Wien2kCommonRelaxWorkChain"""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        _filepath = os.path.join(os.path.dirname(__file__), 'protocol.yml')

        with open(_filepath, encoding='utf-8') as _thefile:
            self._protocols = yaml.full_load(_thefile)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE,))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE,))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('wien2k-run123_lapw')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        reference_workchain = kwargs.get('reference_workchain', None)
        electronic_type = kwargs['electronic_type']

        # Checks
        if protocol not in self.get_protocol_names():
            import warnings

            warnings.warn(f'no protocol implemented with name {protocol}, using default moderate')
            protocol = self.get_default_protocol_name()
        if not all(x in engines.keys() for x in ['relax']):
            raise ValueError('The `engines` dictionary must contain "relax" as outermost key')

        # construct input for run123_lapw
        inpdict = orm.Dict(
            dict={
                '-red': self._protocols[protocol]['parameters']['red'],
                '-i': self._protocols[protocol]['parameters']['max-scf-iterations'],
                '-ec': self._protocols[protocol]['parameters']['scf-ene-tol-Ry'],
                '-cc': self._protocols[protocol]['parameters']['scf-charge-tol'],
                '-fermits': self._protocols[protocol]['parameters']['fermi-temp-Ry'],
                '-nokshift': self._protocols[protocol]['parameters']['nokshift'],
                '-noprec': self._protocols[protocol]['parameters']['noprec'],
                '-numk': self._protocols[protocol]['parameters']['numk'],
                '-numk2': self._protocols[protocol]['parameters']['numk2'],
                '-p': self._protocols[protocol]['parameters']['parallel'],
            }
        )
        if electronic_type == ElectronicType.INSULATOR:
            inpdict['-nometal'] = True
        if reference_workchain:  # ref. workchain is passed as input
            # derive Rmt's from the ref. workchain and pass as input
            w2k_wchain = reference_workchain.base.links.get_outgoing(node_class=orm.WorkChainNode).one().node
            ref_wrkchn_res_dict = w2k_wchain.outputs.workchain_result.get_dict()
            rmt = ref_wrkchn_res_dict['Rmt']
            atm_lbl = ref_wrkchn_res_dict['atom_labels']
            if len(rmt) != len(atm_lbl):
                raise ValueError(f'The list of rmt radii does not match the list of elements: {rmt} and {atm_lbl}')
            inpdict['-red'] = ','.join([f'{a}:{r}' for a, r in zip(atm_lbl, rmt)])
            # derive k mesh from the ref. workchain and pass as input
            if 'kmesh3' in ref_wrkchn_res_dict and ref_wrkchn_res_dict['kmesh3']:  # check if kmesh3 is in results dict
                inpdict['-numk'] = '0' + ' ' + ref_wrkchn_res_dict['kmesh3']
            if (
                'kmesh3k' in ref_wrkchn_res_dict and ref_wrkchn_res_dict['kmesh3k']
            ):  # check if kmesh3k is in results dict
                inpdict['-numk2'] = '0' + ' ' + ref_wrkchn_res_dict['kmesh3k']
            if (
                'fftmesh3k' in ref_wrkchn_res_dict and ref_wrkchn_res_dict['fftmesh3k']
            ):  # check if fftmesh3k is in results dict
                inpdict['-fft'] = ref_wrkchn_res_dict['fftmesh3k']

        # res = NodeNumberJobResource(num_machines=8, num_mpiprocs_per_machine=1, num_cores_per_mpiproc=1)
        builder = self.process_class.get_builder()
        builder.aiida_structure = structure
        builder.code = engines['relax']['code']  # load wien2k-run123_lapw code
        builder.options = orm.Dict(dict=engines['relax']['options'])
        builder.inpdict = inpdict

        return builder
