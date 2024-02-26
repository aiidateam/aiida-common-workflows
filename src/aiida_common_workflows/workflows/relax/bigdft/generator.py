"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for BigDFT."""
import typing as t

from aiida import engine, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('BigDftCommonRelaxInputGenerator',)

BigDFTParameters = plugins.DataFactory('bigdft')
StructureData = plugins.DataFactory('core.structure')


class BigDftCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `BigDftCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols: t.ClassVar = {
        'fast': {
            'description': 'This profile should be chosen if accurate forces are required, but there is no need for '
            'extremely accurate energies.',
            'inputdict_cubic': {
                'logfile': 'Yes',
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.4,
                    'disablesym': 'no',
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.0e-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0,
                },
            },
            'inputdict_linear': {'import': 'linear'},
            'kpoints_distance': 142,  # Equivalent length of K-space resolution (Bohr)
        },
        'moderate': {
            'description': 'This profile should be chosen if accurate forces are required, but there is no need for '
            'extremely accurate energies.',
            'inputdict_cubic': {
                'logfile': 'Yes',
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.4,
                    'disablesym': 'no',
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.0e-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0,
                },
            },
            'inputdict_linear': {'import': 'linear'},
            'kpoints_distance': 274,
        },
        'precise': {
            'description': 'This profile should be chosen if accurate forces are required, but there is no need for '
            'extremely accurate energies.',
            'inputdict_cubic': {
                'logfile': 'Yes',
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.3,
                    'disablesym': 'no',
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.0e-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0,
                },
            },
            'inputdict_linear': {'import': 'linear'},
            'kpoints_distance': 274,
        },
        'verification-PBE-v1': {
            'description': 'Protocol used for bulk run of EoS verification project',
            'inputdict_cubic': {
                'logfile': 'Yes',
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.4,
                    'disablesym': 'no',
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.0e-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0,
                },
            },
            'inputdict_linear': {'import': 'linear'},
            'kpoints_distance': 274,
        },
    }

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['protocol'].valid_type = ChoiceType(('fast', 'moderate', 'precise', 'verification-PBE-v1'))
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE, RelaxType.POSITIONS))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('bigdft')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        import copy

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        electronic_type = kwargs['electronic_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        builder = self.process_class.get_builder()

        builder.BigDFT.structure = structure

        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        if len(builder.BigDFT.structure.sites) <= 200:
            inputdict = copy.deepcopy(self.get_protocol(protocol)['inputdict_cubic'])
        else:
            inputdict = copy.deepcopy(self.get_protocol(protocol)['inputdict_linear'])

        # adapt hgrid to the strain
        if reference_workchain is not None and reference_workchain.is_finished_ok:
            logfile = reference_workchain.outputs.bigdft_logfile.logfile
            if isinstance(logfile, list):
                hgrids = logfile[0].get('dft').get('hgrids')
            else:
                hgrids = logfile.get('dft').get('hgrids')
            first_hgrid = hgrids[0] if isinstance(hgrids, list) else hgrids
            inputdict['dft']['hgrids'] = (
                first_hgrid
                * builder.BigDFT.structure.cell_lengths[0]
                / reference_workchain.inputs.structure.cell_lengths[0]
            )

        if electronic_type is ElectronicType.METAL:
            if 'mix' not in inputdict:
                inputdict['mix'] = {}
            inputdict['mix'].update(
                {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.0e-12,
                    'norbsempty': 120,
                    'tel': 0.01,
                    'alphamix': 0.8,
                    'alphadiis': 1.0,
                }
            )
        if spin_type is SpinType.NONE:
            inputdict['dft'].update({'nspin': 1})
        elif spin_type is SpinType.COLLINEAR:
            inputdict['dft'].update({'nspin': 2})

        if magnetization_per_site:
            for i, atom in enumerate(inputdict['posinp']['positions']):
                atom['IGSpin'] = int(magnetization_per_site[i])
        # correctly set kpoints from protocol fast and moderate. If precise, use the ones from set_inputfile/set_kpt
        if self.get_protocol(protocol).get('kpoints_distance'):
            inputdict['kpt'] = {'method': 'auto', 'kptrlen': self.get_protocol(protocol).get('kpoints_distance')}

        if relax_type == RelaxType.POSITIONS:
            inputdict['geopt'] = {
                'method': 'FIRE',
                'forcemax': threshold_forces or 0,
            }
        elif relax_type == RelaxType.NONE:
            pass
        else:
            raise ValueError(f'relaxation type `{relax_type.value}` is not supported')

        builder.BigDFT.parameters = BigDFTParameters(dict=inputdict)
        builder.BigDFT.code = engines['relax']['code']
        builder.BigDFT.metadata = {'options': engines['relax']['options']}

        return builder
