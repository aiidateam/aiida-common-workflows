# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for BigDFT."""
import os

from aiida import engine, orm, plugins
from aiida.engine import calcfunction

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('BigDftCommonRelaxInputGenerator',)

BigDFTParameters = plugins.DataFactory('bigdft')
StructureData = plugins.DataFactory('structure')


class BigDftCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `BigDftCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
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
                    'disablesym': 'no'
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.E-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0
                }
            },
            'inputdict_linear': {
                'import': 'linear'
            },
            'kpoints_distance': 142
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
                    'disablesym': 'no'
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.E-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0
                }
            },
            'inputdict_linear': {
                'import': 'linear'
            },
            'kpoints_distance': 274
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
                    'disablesym': 'no'
                },
                'mix': {
                    'iscf': 17,
                    'itrpmax': 200,
                    'rpnrm_cv': 1.E-12,
                    'norbsempty': 120,
                    'tel': 0.00225,
                    'occopt': 2,
                    'alphamix': 0.8,
                    'alphadiis': 1.0
                }
            },
            'inputdict_linear': {
                'import': 'linear'
            },
            'kpoints_distance': 274
        }
    }

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE, RelaxType.POSITIONS))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('bigdft')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        import copy

        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
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

        if relax_type == RelaxType.POSITIONS:
            relaxation_schema = 'relax'
        elif relax_type == RelaxType.NONE:
            relaxation_schema = 'relax'
            builder.relax.perform = orm.Bool(False)
        else:
            raise ValueError(f'relaxation type `{relax_type.value}` is not supported')

        builder.structure = structure

        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        if len(builder.structure.sites) <= 200:
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
            hg = hgrids[0] if isinstance(hgrids, list) else hgrids
            inputdict['dft']['hgrids'] = hg * builder.structure.cell_lengths[0] / \
                reference_workchain.inputs.structure.cell_lengths[0]

        if electronic_type is ElectronicType.METAL:
            if 'mix' not in inputdict:
                inputdict['mix'] = {}
            inputdict['mix'].update({
                'iscf': 17,
                'itrpmax': 200,
                'rpnrm_cv': 1.E-12,
                'norbsempty': 120,
                'tel': 0.01,
                'alphamix': 0.8,
                'alphadiis': 1.0
            })
        if spin_type is SpinType.NONE:
            inputdict['dft'].update({'nspin': 1})
        elif spin_type is SpinType.COLLINEAR:
            inputdict['dft'].update({'nspin': 2})

        if magnetization_per_site:
            for (i, atom) in enumerate(inputdict['posinp']['positions']):
                atom['IGSpin'] = int(magnetization_per_site[i])
        # correctly set kpoints from protocol fast and moderate. If precise, use the ones from set_inputfile/set_kpt
        if self.get_protocol(protocol).get('kpoints_distance'):
            inputdict['kpt'] = {'method': 'auto', 'kptrlen': self.get_protocol(protocol).get('kpoints_distance')}
        # # update the dict with acwf parameters for further treating
        # acwf_params = {'electronic_type': electronic_type.value,
        #                'relax_type': relax_type.value,
        #                'spin_type': spin_type.value,
        #                'protocol': protocol}
        # inputdict['acwf_params'] = acwf_params

        builder.parameters = BigDFTParameters(dict=inputdict)
        builder.code = engines[relaxation_schema]['code']
        run_opts = {'options': engines[relaxation_schema]['options']}
        builder.run_opts = orm.Dict(dict=run_opts)

        if threshold_forces is not None:
            builder.relax.threshold_forces = orm.Float(threshold_forces)

        return builder

def print_dict(d, prefix: str = '', indent = 0):

    indent_str = '    ' * indent

    if isinstance(d, dict):
        for k, v in d.items():
            print(f'{indent_str}{k}:')
            print_dict(v, indent = indent + 1)
    elif hasattr(d, '__iter__') and not isinstance(d, str):
        for item in d:
            print_dict(item, prefix = '- ', indent = indent)
    else:
        print(f'{indent_str}{prefix}{d}')
