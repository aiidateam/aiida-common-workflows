# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Gaussian."""

from aiida import orm
from aiida import plugins

from ..generator import RelaxInputsGenerator, RelaxType

__all__ = ('GaussianRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class GaussianRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `GaussianRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'Optimal performance, minimal accuracy.',
            'functional': 'PBEPBE',
            'basis_set': 'STO-3G',
            'route_parameters': {
                'nosymm': None,
                'opt': None,
            }
        },
        'moderate': {
            'description': 'Moderate performance, moderate accuracy.',
            'functional': 'PBEPBE',
            'basis_set': '6-31+G(d,p)',
            'route_parameters': {
                'int': 'ultrafine',
                'nosymm': None,
                'opt': 'tight',
            }
        },
        'precise': {
            'description': 'Low performance, high accuracy',
            'functional': 'PBEPBE',
            'basis_set': '6-311+G(d,p)',
            'route_parameters': {
                'int': 'superfine',
                'nosymm': None,
                'opt': 'tight',
            }
        }
    }

    _calc_types = {'relax': {'code_plugin': 'gaussian', 'description': 'The code to perform the relaxation.'}}
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
        previous_workchain=None,
        **kwargs
    ):
        # pylint: disable=too-many-locals
        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            **kwargs
        )

        if relaxation_type != RelaxType.ATOMS:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        # -----------------------------------------------------------------
        # Set the link0 memory and n_proc based on the calc_engines options dict

        link0_parameters = {'%chk': 'aiida.chk'}

        options = calc_engines['relax']['options']

        # If memory is not set, Gaussian uses a default of 800 MB
        # If memory is set, there should be extra ~1.5 GB reserved compared to what is specified to gaussian
        if 'max_memory_kb' in options:
            mem_mb = options['max_memory_kb'] // 1024
            if mem_mb > 1600:
                link0_parameters['%mem'] = '%dMB' % (mem_mb - 1500)

        res = options['resources']
        n_proc = None
        if 'tot_num_mpiprocs' in res:
            n_proc = res['tot_num_mpiprocs']
        elif 'num_machines' in res and 'num_mpiprocs_per_machine' in res:
            n_proc = res['num_machines'] * res['num_mpiprocs_per_machine']

        if n_proc is not None:
            link0_parameters['%nprocshared'] = '%d' % n_proc

        # -----------------------------------------------------------------

        sel_protocol = self.get_protocol(protocol)

        params = {
            'link0_parameters': link0_parameters,
            'functional': sel_protocol['functional'],
            'basis_set': sel_protocol['basis_set'],
            'charge': 0,
            'multiplicity': 1,
            'route_parameters': sel_protocol['route_parameters']
        }

        builder = self.process_class.get_builder()

        builder.gaussian.structure = structure

        builder.gaussian.parameters = orm.Dict(dict=params)

        builder.gaussian.code = orm.load_code(calc_engines['relax']['code'])

        builder.gaussian.metadata.options = calc_engines['relax']['options']

        return builder
