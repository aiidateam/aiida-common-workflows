"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Gaussian."""
import copy
import typing as t

import numpy as np
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('GaussianCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')

EV_TO_EH = 0.03674930814
ANG_TO_BOHR = 1.88972687


class GaussianCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `GaussianCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols: t.ClassVar = {
        'fast': {
            'description': 'Optimal performance, minimal accuracy.',
            'functional': 'PBEPBE',
            'basis_set': 'Def2SVP',
            'route_parameters': {
                'nosymm': None,
                'opt': 'loose',
            },
        },
        'moderate': {
            'description': 'Moderate performance, moderate accuracy.',
            'functional': 'PBEPBE',
            'basis_set': 'Def2TZVP',
            'route_parameters': {
                'int': 'ultrafine',
                'nosymm': None,
                'opt': None,
            },
        },
        'precise': {
            'description': 'Low performance, high accuracy',
            'functional': 'PBEPBE',
            'basis_set': 'Def2QZVP',
            'route_parameters': {
                'int': 'superfine',
                'nosymm': None,
                'opt': 'tight',
            },
        },
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
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('gaussian')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)

        if any(structure.base.attributes.get_many(['pbc1', 'pbc2', 'pbc3'])):
            print('Warning: PBC detected in input structure. It is not supported and thus ignored.')

        # -----------------------------------------------------------------
        # Set the link0 memory and n_proc based on the engines options dict

        link0_parameters = {'%chk': 'aiida.chk'}

        options = engines['relax']['options']
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
                code = engines['relax']['code']
                def_mppm = code.computer.get_default_mpiprocs_per_machine()
                if def_mppm is not None:
                    n_proc = res['num_machines'] * def_mppm

        if n_proc is not None:
            link0_parameters['%nprocshared'] = int(n_proc)
        # -----------------------------------------------------------------
        # General route parameters

        sel_protocol = copy.deepcopy(self.get_protocol(protocol))
        route_params = sel_protocol['route_parameters']

        if relax_type == RelaxType.NONE:
            del route_params['opt']
            route_params['force'] = None

        if threshold_forces is not None:
            # Set the RMS force threshold with the iop(1/7=N) command
            # threshold = N * 10**(-6) in [EH/Bohr]
            threshold_forces_au = threshold_forces * EV_TO_EH / ANG_TO_BOHR
            if threshold_forces_au < 1e-6:
                print('Warning: Forces threshold cannot be lower than 1e-6 au.')
                threshold_forces_au = 1e-6
            threshold_forces_n = int(np.round(threshold_forces_au * 1e6))
            route_params[f'iop(1/7={threshold_forces_n})'] = None

        # -----------------------------------------------------------------
        # Handle spin-polarization

        pymatgen_structure = structure.get_pymatgen_molecule()
        num_electrons = pymatgen_structure.nelectrons
        spin_multiplicity = 1

        if num_electrons % 2 == 1 and spin_type == SpinType.NONE:
            raise ValueError(f'Spin-restricted calculation does not support odd number of electrons ({num_electrons})')

        if spin_type == SpinType.COLLINEAR:
            # enable UKS
            sel_protocol['functional'] = 'U' + sel_protocol['functional']

            # determine the spin multiplicity

            if magnetization_per_site is None:
                multiplicity_guess = 1
            else:
                print(
                    'Warning: magnetization_per_site site-resolved info is disregarded, only total spin is processed.'
                )
                # magnetization_per_site are in units of [Bohr magnetons] (*0.5 to get in [au])
                total_spin_guess = 0.5 * np.abs(np.sum(magnetization_per_site))
                multiplicity_guess = 2 * total_spin_guess + 1

            # in case of even/odd electrons, find closest odd/even multiplicity
            if num_electrons % 2 == 0:
                # round guess to nearest odd integer
                spin_multiplicity = int(np.round((multiplicity_guess - 1) / 2) * 2 + 1)
            else:
                # round guess to nearest even integer; 0 goes to 2
                spin_multiplicity = max([int(np.round(multiplicity_guess / 2) * 2), 2])

            # Mix HOMO and LUMO if we're looking for the open-shell singlet
            if spin_multiplicity == 1:
                route_params['guess'] = 'mix'

        # -----------------------------------------------------------------
        # Build the builder

        params = {
            'link0_parameters': link0_parameters,
            'functional': sel_protocol['functional'],
            'basis_set': sel_protocol['basis_set'],
            'charge': 0,
            'multiplicity': spin_multiplicity,
            'route_parameters': route_params,
        }

        builder = self.process_class.get_builder()
        builder.gaussian.structure = structure
        builder.gaussian.parameters = orm.Dict(dict=params)
        builder.gaussian.code = engines['relax']['code']
        builder.gaussian.metadata.options = engines['relax']['options']

        return builder
