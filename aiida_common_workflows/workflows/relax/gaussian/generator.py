# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Gaussian."""

import copy
import numpy as np

from aiida import orm
from aiida import plugins

from aiida.orm import load_code

from ..generator import RelaxInputsGenerator, RelaxType, SpinType

__all__ = ('GaussianRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')

EV_TO_EH = 0.03674930814
ANG_TO_BOHR = 1.88972687


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
        is_insulator=False,
        spin_type=SpinType.NONE,
        magnetization_per_site=None,
        **kwargs
    ):
        # pylint: disable=too-many-locals
        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            is_insulator, spin_type, magnetization_per_site, **kwargs
        )

        if relaxation_type != RelaxType.ATOMS:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        # -----------------------------------------------------------------
        # Set the link0 memory and n_proc based on the calc_engines options dict

        link0_parameters = {'%chk': 'aiida.chk'}

        options = calc_engines['relax']['options']
        res = options['resources']

        if 'max_memory_kb' not in options:
            # If memory is not set, set a default of 2 GB
            link0_parameters['%mem'] = '2048MB'
        else:
            # If memory is set, specify 80% of it to gaussian
            link0_parameters['%mem'] = '%dMB' % ((0.8 * options['max_memory_kb']) // 1024)

        # Determine the number of processors that should be specified to Gaussian
        n_proc = None
        if 'tot_num_mpiprocs' in res:
            n_proc = res['tot_num_mpiprocs']
        elif 'num_machines' in res:
            if 'num_mpiprocs_per_machine' in res:
                n_proc = res['num_machines'] * res['num_mpiprocs_per_machine']
            else:
                code = load_code(calc_engines['relax']['code'])
                def_mppm = code.computer.get_default_mpiprocs_per_machine()
                if def_mppm is not None:
                    n_proc = res['num_machines'] * def_mppm

        if n_proc is not None:
            link0_parameters['%nprocshared'] = '%d' % n_proc
        # -----------------------------------------------------------------

        sel_protocol = copy.deepcopy(self.get_protocol(protocol))

        route_params = sel_protocol['route_parameters']

        if threshold_forces is not None:
            # Set the RMS force threshold with the iop(1/7=N) command
            # threshold = N * 10**(-6) in [EH/Bohr]
            threshold_forces_au = threshold_forces * EV_TO_EH / ANG_TO_BOHR
            if threshold_forces_au < 1e-6:
                print('Warning: Forces threshold cannot be lower than 1e-6 au.')
                threshold_forces_au = 1e-6
            threshold_forces_n = int(np.round(threshold_forces_au * 1e6))
            route_params['iop(1/7=%d)' % threshold_forces_n] = None

        params = {
            'link0_parameters': link0_parameters,
            'functional': sel_protocol['functional'],
            'basis_set': sel_protocol['basis_set'],
            'charge': 0,
            'multiplicity': 1,
            'route_parameters': route_params
        }

        builder = self.process_class.get_builder()

        builder.gaussian.structure = structure

        builder.gaussian.parameters = orm.Dict(dict=params)

        builder.gaussian.code = orm.load_code(calc_engines['relax']['code'])

        builder.gaussian.metadata.options = calc_engines['relax']['options']

        return builder
