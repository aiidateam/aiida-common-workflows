# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for BigDFT."""
from aiida import orm
from aiida.plugins import DataFactory
from ..generator import RelaxInputsGenerator, RelaxType
from .workchain import BigDFTCommonRelaxWorkChain

__all__ = ('BigDFTRelaxInputsGenerator',)

BigDFTParameters = DataFactory('bigdft')


class BigDFTRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `BigDFTRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'This profile should be chosen if speed\
 is more important than accuracy.',
            'inputdict_cubic': {
                'dft': {
                    'hgrids': 0.45
                }
            },
            'inputdic_linear': {
                'import': 'linear_fast'
            }
        },
        'moderate': {
            'description': 'This profile should be chosen if accurate forces \
are required, but there is no need for extremely \
accurate energies.',
            'inputdict_cubic': {},
            'inputdict_linear': {
                'import': 'linear'
            }
        },
        'precise': {
            'description': 'This profile should be chosen if highly accurate\
                            energy differences are required.',
            'inputdict_cubic': {
                'dft': {
                    'hgrids': 0.15
                }
            },
            'inputdict_linear': {
                'import': 'linear_accurate'
            }
        }
    }

    _calc_types = {'relax': {'code_plugin': 'bigdft.bigdft', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
    }

    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        **kwargs
    ):

        from aiida.orm import Dict
        from aiida.orm import load_code

        if relaxation_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        builder = BigDFTCommonRelaxWorkChain.get_builder()
        builder.structure = structure

        #Will be implemented in the bigdft plugin
        #inputdict = BigDFTParameters.get_input_dict(protocol, structure, 'relax')
        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        if len(structure.sites) <= 200:
            inputdict = self.get_protocol(protocol)['inputdict_cubic']
        else:
            inputdict = self.get_protocol(protocol)['inputdict_linear']

        builder.parameters = BigDFTParameters(dict=inputdict)
        builder.code = load_code(calc_engines[relaxation_schema]['code'])
        run_opts = {'options': calc_engines[relaxation_schema]['options']}
        builder.run_opts = Dict(dict=run_opts)

        if threshold_forces is not None:
            builder.relax.threshold_forces = orm.Float(threshold_forces)

        return builder
