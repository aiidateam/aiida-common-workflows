"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for CP2K."""
import collections
import pathlib
import typing as t

import numpy as np
import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('Cp2kCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')
KpointsData = plugins.DataFactory('core.array.kpoints')

EV_A3_TO_GPA = 160.21766208


def dict_merge(dct, merge_dct):
    """Taken from https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k in merge_dct.keys():
        if k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], collections.abc.Mapping):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def get_kinds_section(structure: StructureData, basis_pseudo=None, magnetization_tags=None, use_sirius=False):
    """Write the &KIND sections given the structure and the settings_dict."""
    kinds = []
    if not use_sirius:
        with open(pathlib.Path(__file__).parent / basis_pseudo, 'rb') as fhandle:
            atom_data = yaml.safe_load(fhandle)
    ase_structure = structure.get_ase()
    symbol_tag = {
        (symbol, str(tag)) for symbol, tag in zip(ase_structure.get_chemical_symbols(), ase_structure.get_tags())
    }
    for symbol, tag in symbol_tag:
        new_atom = {
            '_': symbol if tag == '0' else symbol + tag,
        }
        if use_sirius:
            new_atom['POTENTIAL'] = f'UPF {symbol}.json'
        else:
            new_atom['BASIS_SET'] = atom_data['basis_set'][symbol]
            new_atom['POTENTIAL'] = atom_data['pseudopotential'][symbol]
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


def guess_multiplicity(structure: StructureData, magnetization_per_site: t.Optional[t.List[float]] = None):
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
    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT', 'rb') as handle:
        basis_molopt = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT_UZH', 'rb') as handle:
        basis_molopt_uzh = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT_UCL', 'rb') as handle:
        basis_molopt_ucl = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'GTH_BASIS_SETS', 'rb') as handle:
        basis_gth = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'GTH_POTENTIALS', 'rb') as handle:
        potential = orm.SinglefileData(file=handle)

    return {
        'basis_molopt': basis_molopt,
        'basis_molopt_uzh': basis_molopt_uzh,
        'basis_molopt_ucl': basis_molopt_ucl,
        'basis_gth': basis_gth,
        'potential': potential,
    }


def get_upf_pseudos_section(structure: StructureData, pseudo_family):
    """Provide the pseudos section to the input."""
    pseudos_group = orm.load_group(pseudo_family)
    return pseudos_group.get_pseudos(structure=structure)


class Cp2kCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `Cp2kRelaxWorkChain`."""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(pathlib.Path(__file__).parent / 'protocol.yml', 'rb') as handle:
            self._protocols = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['protocol'].valid_type = ChoiceType(
            ('fast', 'moderate', 'precise', 'verification-PBE-v1', 'verification-PBE-v1-sirius')
        )
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            (RelaxType.NONE, RelaxType.POSITIONS, RelaxType.POSITIONS_CELL)
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('cp2k')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        electronic_type = kwargs['electronic_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # The builder.
        builder = self.process_class.get_builder()

        # Protocol input.
        protocol_dict = self.get_protocol(protocol)
        parameters = protocol_dict.pop('input')

        # Kpoints.
        kpoints_distance = protocol_dict.pop('kpoints_distance', None)
        kpoints = self._get_kpoints(kpoints_distance, structure, reference_workchain)
        mesh, _ = kpoints.get_kpoints_mesh()
        if 'sirius' in protocol:
            parameters['FORCE_EVAL']['PW_DFT']['PARAMETERS']['NGRIDK'] = f'{mesh[0]} {mesh[1]} {mesh[2]}'
        elif mesh != [1, 1, 1]:
            builder.cp2k.kpoints = kpoints

        magnetization_tags = None

        # Metal or insulator.
        if 'sirius' not in protocol:  # It is not possible to disable smearing for sirius.
            # If metal then add smearing, unoccupied orbitals, and employ diagonalization.
            if electronic_type == ElectronicType.METAL:
                parameters['FORCE_EVAL']['DFT']['SCF']['SMEAR'] = {
                    '_': 'ON',
                    'METHOD': 'FERMI_DIRAC',
                    'ELECTRONIC_TEMPERATURE': '[K] 710.5',
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
                parameters['FORCE_EVAL']['DFT']['SCF']['CHOLESKY'] = 'OFF'

            # If insulator then employ OT.
            elif electronic_type == ElectronicType.INSULATOR:
                parameters['FORCE_EVAL']['DFT']['SCF']['OT'] = {
                    'PRECONDITIONER': 'FULL_SINGLE_INVERSE',
                    'MINIMIZER': 'CG',
                }

            # Magnetic calculation. Changing this configuration has no effect on sirius calculations.
            if spin_type == SpinType.NONE:
                parameters['FORCE_EVAL']['DFT']['UKS'] = False
                if magnetization_per_site is not None:
                    import warnings

                    warnings.warn('`magnetization_per_site` will be ignored as `spin_type` is set to SpinType.NONE')

            elif spin_type == SpinType.COLLINEAR:
                parameters['FORCE_EVAL']['DFT']['UKS'] = True
                structure, magnetization_tags = tags_and_magnetization(structure, magnetization_per_site)
                parameters['FORCE_EVAL']['DFT']['MULTIPLICITY'] = guess_multiplicity(structure, magnetization_per_site)

        # Starting magnetization.
        basis_pseudo = protocol_dict.pop('basis_pseudo')
        if 'sirius' in protocol:
            dict_merge(
                parameters,
                get_kinds_section(structure, basis_pseudo=None, magnetization_tags=magnetization_tags, use_sirius=True),
            )
        else:
            dict_merge(
                parameters,
                get_kinds_section(
                    structure, basis_pseudo=basis_pseudo, magnetization_tags=magnetization_tags, use_sirius=False
                ),
            )

        # Relaxation type.
        if relax_type == RelaxType.POSITIONS:
            run_type = 'GEO_OPT'
        elif relax_type == RelaxType.POSITIONS_CELL:
            run_type = 'CELL_OPT'
        elif relax_type == RelaxType.NONE:
            run_type = 'ENERGY_FORCE'
        else:
            raise ValueError(f'Relax type `{relax_type.value}` is not supported')
        parameters.setdefault('GLOBAL', {})['RUN_TYPE'] = run_type

        # Redefining forces threshold.
        if threshold_forces is not None:
            parameters['MOTION'][run_type]['MAX_FORCE'] = f'[eV/angstrom] {threshold_forces}'

        # Redefining stress threshold.
        if threshold_stress is not None:
            parameters['MOTION']['CELL_OPT']['PRESSURE_TOLERANCE'] = f'[GPa] {threshold_stress * EV_A3_TO_GPA}'

        # Lowering runtime by 5 minutes to let CP2K gracefully finish the calculation.
        try:
            walltime = engines['relax']['options']['max_wallclock_seconds']
            walltime = max(300, walltime - 300)
            parameters['GLOBAL']['WALLTIME'] = walltime
        except KeyError:
            pass

        # Setup a CELL_REF.
        try:
            scale_factor = protocol_dict.pop('cell_ref_scale_factor')
        except KeyError:
            pass  # If the protocol does not specify a CELL_REF factor, ignore it (CP2K will use the structure cell).
        else:
            # Otherwise, create necessary subdicts (unlikely to exist since CELL is written based on the structure)
            parameters['FORCE_EVAL'].setdefault('SUBSYS', {}).setdefault('CELL', {})['CELL_REF'] = self._get_cell_ref(
                structure, reference_workchain, scale_factor
            )

        builder.cp2k.parameters = orm.Dict(dict=parameters)

        # Switch on the resubmit_unconverged_geometry which is disabled by default.
        builder.handler_overrides = orm.Dict(dict={'restart_incomplete_calculation': {'enabled': True}})

        # Files.
        if 'sirius' in protocol:
            builder.cp2k.pseudos_upf = get_upf_pseudos_section(structure, basis_pseudo)
        else:
            builder.cp2k.file = get_file_section()

        # Input structure.
        builder.cp2k.structure = structure

        # Additional files to be retrieved.
        builder.cp2k.settings = orm.Dict(
            dict={'additional_retrieve_list': ['aiida-frc-1.xyz', 'aiida-1.stress', 'aiida-requested-forces-1_0.xyz']}
        )

        # CP2K code.
        builder.cp2k.code = engines['relax']['code']

        # Run options.
        builder.cp2k.metadata.options = engines['relax']['options']

        # Use advanced parser to parse more data.
        builder.cp2k.metadata.options['parser_name'] = 'cp2k_advanced_parser'

        return builder

    @staticmethod
    def _get_kpoints(kpoints_distance, structure, reference_workchain):
        if reference_workchain and 'cp2k__kpoints' in reference_workchain.inputs:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kpoints_mesh.set_kpoints_mesh(reference_workchain.inputs.cp2k__kpoints.base.attributes.get('mesh'))
            return kpoints_mesh

        if kpoints_distance:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kpoints_mesh.set_kpoints_mesh_from_density(distance=kpoints_distance)
            return kpoints_mesh
        return None

    @staticmethod
    def _get_cell_ref(structure, reference_workchain, scale_factor):
        """If the reference_workchain specifies a CELL_REF, return that one, otherwise generate one"""

        if reference_workchain and 'cp2k__parameters' in reference_workchain.inputs:
            try:
                return reference_workchain.inputs.cp2k.parameters['FORCE_EVAL']['SUBSYS']['CELL']['CELL_REF']
            except KeyError:
                # here we assume that the ref_cell_scale_factor is the same for both the reference
                # workchain and any subsequent workchains
                pass

        cell = [[v * scale_factor ** (1 / 3) for v in row] for row in structure.cell]

        # start with an A, B, C:
        cell_ref = {idx: f'[angstrom] {row[0]:<15} {row[1]:<15} {row[2]:<15}' for idx, row in zip('ABC', cell)}
        # then add periodicity information matching the structure
        cell_ref['PERIODIC'] = ''.join(axis * enabled for axis, enabled in zip('XYZ', structure.pbc))
        return cell_ref
