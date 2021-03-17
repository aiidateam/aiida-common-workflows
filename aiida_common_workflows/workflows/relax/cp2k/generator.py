# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for CP2K."""
import collections
import pathlib
from typing import Any, Dict, List
import yaml
import numpy as np

from aiida import engine
from aiida import orm
from aiida import plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('Cp2kCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')  # pylint: disable=invalid-name
KpointsData = plugins.DataFactory('array.kpoints')  # pylint: disable=invalid-name

EV_A3_TO_GPA = 160.21766208


def dict_merge(dct, merge_dct):
    """ Taken from https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k in merge_dct.keys():
        if (k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def get_kinds_section(structure: StructureData, magnetization_tags=None):
    """ Write the &KIND sections given the structure and the settings_dict"""
    kinds = []
    with open(pathlib.Path(__file__).parent / 'atomic_kinds.yml') as fhandle:
        atom_data = yaml.safe_load(fhandle)
    ase_structure = structure.get_ase()
    symbol_tag = {
        (symbol, str(tag)) for symbol, tag in zip(ase_structure.get_chemical_symbols(), ase_structure.get_tags())
    }
    for symbol, tag in symbol_tag:
        new_atom = {
            '_': symbol if tag == '0' else symbol + tag,
            'BASIS_SET': atom_data['basis_set'][symbol],
            'POTENTIAL': atom_data['pseudopotential'][symbol],
        }
        if magnetization_tags:
            new_atom['MAGNETIZATION'] = magnetization_tags[tag]
        kinds.append(new_atom)
    return {'FORCE_EVAL': {'SUBSYS': {'KIND': kinds}}}


def tags_and_magnetization(structure, magnetization_per_site):
    """Gather the same atoms with the same magnetization into one atomic kind."""
    if magnetization_per_site:
        ase_structure = structure.get_ase()
        if len(magnetization_per_site) != len(ase_structure.numbers):
            raise ValueError('The size of `magnetization_per_site` is different from the number of atoms.')

        # Combine atom type with magnetizations.
        complex_symbols = [
            f'{symbol}_{magn}' for symbol, magn in zip(ase_structure.get_chemical_symbols(), magnetization_per_site)
        ]
        # Assign a unique tag for every atom kind.
        combined = {symbol: tag + 1 for tag, symbol in enumerate(set(complex_symbols))}
        # Assigning correct tags to every atom.
        tags = [combined[key] for key in complex_symbols]
        ase_structure.set_tags(tags)
        # Tag-magnetization correspondance.
        tags_correspondance = {str(value): float(key.split('_')[1]) for key, value in combined.items()}
        return StructureData(ase=ase_structure), orm.Dict(dict=tags_correspondance)
    return structure, None


def guess_multiplicity(structure: StructureData, magnetization_per_site: List[float] = None):
    """Get total spin multiplicity from atomic magnetizations."""
    spin_multiplicity = 1
    if magnetization_per_site:
        pymatgen_structure = structure.get_pymatgen_molecule()
        num_electrons = pymatgen_structure.nelectrons
        total_spin_guess = 0.5 * np.abs(np.sum(magnetization_per_site))
        multiplicity_guess = 2 * total_spin_guess + 1

        # In case of even/odd electrons, find closest odd/even multiplicity
        if num_electrons % 2 == 0:
            # round guess to nearest odd integer
            spin_multiplicity = int(np.round((multiplicity_guess - 1) / 2) * 2 + 1)
        else:
            # round guess to nearest even integer; 0 goes to 2
            spin_multiplicity = max([int(np.round(multiplicity_guess / 2) * 2), 2])
    return spin_multiplicity


def get_file_section():
    """Provide necessary parameter files such as pseudopotientials, basis sets, etc."""
    with open(pathlib.Path(__file__).parent / 'GTH_BASIS_SETS', 'rb') as handle:
        basis_gth = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT', 'rb') as handle:
        basis_molopt = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT_UCL', 'rb') as handle:
        basis_molopt_ucl = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'GTH_POTENTIALS', 'rb') as handle:
        potential = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'dftd3.dat', 'rb') as handle:
        dftd3_params = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'xTB_parameters', 'rb') as handle:
        xtb_params = orm.SinglefileData(file=handle)

    return {
        'basis_gth': basis_gth,
        'basis_molopt': basis_molopt,
        'basis_molopt_ucl': basis_molopt_ucl,
        'potential': potential,
        'dftd3_params': dftd3_params,
        'xtb_dat': xtb_params,
    }


class Cp2kCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `Cp2kRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _engine_types = {'relax': {'code_plugin': 'cp2k', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'No relaxation performed.',
        RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.POSITIONS_CELL: 'Relax both atomic positions and the cell.'
    }
    _spin_types = {
        SpinType.NONE: 'Non magnetic calculation.',
        SpinType.COLLINEAR: 'Magnetic calculation with collinear spins.'
    }
    _electronic_types = {
        ElectronicType.METAL: 'Use smearing (default).',
        ElectronicType.INSULATOR: 'Do not use smearing.'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(pathlib.Path(__file__).parent / 'protocol.yml') as handle:
            self._protocols = yaml.safe_load(handle)

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.POSITIONS,
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
        # pylint: disable=too-many-locals
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

        # The builder.
        builder = self.process_class.get_builder()

        # Input parameters.
        parameters = self.get_protocol(protocol)

        # Kpoints.
        kpoints_distance = parameters.pop('kpoints_distance', None)
        kpoints = self._get_kpoints(kpoints_distance, structure, reference_workchain)
        mesh, _ = kpoints.get_kpoints_mesh()
        if mesh != [1, 1, 1]:
            builder.cp2k.kpoints = kpoints

        # Removing description.
        _ = parameters.pop('description')

        magnetization_tags = None

        # Metal or insulator.
        ## If metal then add smearing, unoccupied orbitals, and employ diagonalization.
        if electronic_type == ElectronicType.METAL:
            parameters['FORCE_EVAL']['DFT']['SCF']['SMEAR'] = {
                '_': 'ON',
                'METHOD': 'FERMI_DIRAC',
                'ELECTRONIC_TEMPERATURE': '[K] 500',
            }
            parameters['FORCE_EVAL']['DFT']['SCF']['DIAGONALIZATION'] = {
                'EPS_ADAPT': '1',
            }
            parameters['FORCE_EVAL']['DFT']['SCF']['MIXING'] = {
                'METHOD': 'BROYDEN_MIXING',
                'ALPHA': '0.1',
                'BETA': '1.5',
            }
            parameters['FORCE_EVAL']['DFT']['SCF']['ADDED_MOS'] = 20

        ## If insulator then employ OT.
        elif electronic_type == ElectronicType.INSULATOR:
            parameters['FORCE_EVAL']['DFT']['SCF']['OT'] = {
                'PRECONDITIONER': 'FULL_SINGLE_INVERSE',
                'MINIMIZER': 'CG',
            }

        ## Magnetic calculation.
        if spin_type == SpinType.NONE:
            parameters['FORCE_EVAL']['DFT']['UKS'] = False
            if magnetization_per_site is not None:
                import warnings
                warnings.warn('`magnetization_per_site` will be ignored as `spin_type` is set to SpinType.NONE')

        elif spin_type == SpinType.COLLINEAR:
            parameters['FORCE_EVAL']['DFT']['UKS'] = True
            structure, magnetization_tags = tags_and_magnetization(structure, magnetization_per_site)
            parameters['FORCE_EVAL']['DFT']['MULTIPLICITY'] = guess_multiplicity(structure, magnetization_per_site)

        ## Starting magnetization.
        dict_merge(parameters, get_kinds_section(structure, magnetization_tags))

        ## Relaxation type.
        if relax_type == RelaxType.POSITIONS:
            run_type = 'GEO_OPT'
        elif relax_type == RelaxType.POSITIONS_CELL:
            run_type = 'CELL_OPT'
        elif relax_type == RelaxType.NONE:
            run_type = 'ENERGY_FORCE'
        else:
            raise ValueError(f'Relax type `{relax_type.value}` is not supported')
        parameters['GLOBAL'] = {'RUN_TYPE': run_type}

        ## Redefining forces threshold.
        if threshold_forces is not None:
            parameters['MOTION'][run_type]['MAX_FORCE'] = f'[eV/angstrom] {threshold_forces}'

        ## Redefining stress threshold.
        if threshold_stress is not None:
            parameters['MOTION']['CELL_OPT']['PRESSURE_TOLERANCE'] = f'[GPa] {threshold_stress * EV_A3_TO_GPA}'
        builder.cp2k.parameters = orm.Dict(dict=parameters)

        # Switch on the resubmit_unconverged_geometry which is disabled by default.
        builder.handler_overrides = orm.Dict(dict={'resubmit_unconverged_geometry': True})

        # Files.
        builder.cp2k.file = get_file_section()

        # Input structure.
        builder.cp2k.structure = structure

        # Additional files to be retrieved.
        builder.cp2k.settings = orm.Dict(
            dict={'additional_retrieve_list': ['aiida-frc-1.xyz', 'aiida-1.stress', 'aiida-requested-forces-1_0.xyz']}
        )

        # CP2K code.
        builder.cp2k.code = orm.load_code(engines['relax']['code'])

        # Run options.
        builder.cp2k.metadata.options = engines['relax']['options']

        # Use advanced parser to parse more data.
        builder.cp2k.metadata.options['parser_name'] = 'cp2k_advanced_parser'

        # Uncomment to change number of CPUs and execution time.
        #builder.cp2k.metadata.options['resources']['num_mpiprocs_per_machine'] = 16
        #builder.cp2k.metadata.options['max_wallclock_seconds'] = 3600 * 72

        return builder

    @staticmethod
    def _get_kpoints(kpoints_distance, structure, reference_workchain):
        if reference_workchain and 'cp2k__kpoints' in reference_workchain.inputs:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kpoints_mesh.set_kpoints_mesh(reference_workchain.inputs.cp2k__kpoints.get_attribute('mesh'))
            return kpoints_mesh

        if kpoints_distance:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kpoints_mesh.set_kpoints_mesh_from_density(distance=kpoints_distance)
            return kpoints_mesh
        return None
