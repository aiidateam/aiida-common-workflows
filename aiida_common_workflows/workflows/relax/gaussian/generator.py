# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Gaussian."""
import copy
from typing import Any, Dict, List

import numpy as np

from aiida import engine
from aiida import orm
from aiida import plugins

from aiida.orm import load_code

from ..generator import RelaxInputGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('GaussianRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')

EV_TO_EH = 0.03674930814
ANG_TO_BOHR = 1.88972687


class GaussianRelaxInputGenerator(RelaxInputGenerator):
    """Input generator for the `GaussianRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'Optimal performance, minimal accuracy.',
            'functional': 'PBEPBE',
            'basis_set': 'Def2SVP',
            'route_parameters': {
                'nosymm': None,
                'opt': None,
            }
        },
        'moderate': {
            'description': 'Moderate performance, moderate accuracy.',
            'functional': 'PBEPBE',
            'basis_set': 'Def2TZVP',
            'route_parameters': {
                'int': 'ultrafine',
                'nosymm': None,
                'opt': 'tight',
            }
        },
        'precise': {
            'description': 'Low performance, high accuracy',
            'functional': 'PBEPBE',
            'basis_set': 'Def2QZVP',
            'route_parameters': {
                'int': 'superfine',
                'nosymm': None,
                'opt': 'tight',
            }
        }
    }

    _engine_types = {'relax': {'code_plugin': 'gaussian', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'Single point calculation.',
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
    }
    _spin_types = {
        SpinType.NONE: 'Restricted Kohn-Sham calculation',
        SpinType.COLLINEAR: 'Unrestricted Kohn-Sham calculation',
    }
    _electronic_types = {ElectronicType.METAL: 'ignored', ElectronicType.INSULATOR: 'ignored'}

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            reference_workchain=reference_workchain,
            **kwargs
        )

        if any(structure.get_attribute_many(['pbc1', 'pbc2', 'pbc3'])):
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
                code = load_code(engines['relax']['code'])
                def_mppm = code.computer.get_default_mpiprocs_per_machine()
                if def_mppm is not None:
                    n_proc = res['num_machines'] * def_mppm

        if n_proc is not None:
            link0_parameters['%nprocshared'] = '%d' % n_proc
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
            route_params['iop(1/7=%d)' % threshold_forces_n] = None

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
            'route_parameters': route_params
        }

        builder = self.process_class.get_builder()
        builder.gaussian.structure = structure
        builder.gaussian.parameters = orm.Dict(dict=params)
        builder.gaussian.code = orm.load_code(engines['relax']['code'])
        builder.gaussian.metadata.options = engines['relax']['options']

        return builder
