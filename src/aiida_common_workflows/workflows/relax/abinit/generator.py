"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for ABINIT."""
import collections
import copy
import pathlib
import typing as t
import warnings

import numpy as np
import yaml
from aiida import engine, orm, plugins
from aiida.common import exceptions
from pymatgen.core import units

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('AbinitCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class AbinitCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `AbinitCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml'), encoding='utf-8') as handle:
            self._protocols = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType(tuple(SpinType))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            [t for t in RelaxType if t not in (RelaxType.VOLUME, RelaxType.SHAPE, RelaxType.CELL)]
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType(
            (ElectronicType.METAL, ElectronicType.INSULATOR, ElectronicType.UNKNOWN)
        )
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('abinit')
        spec.inputs['protocol'].valid_type = ChoiceType(('fast', 'moderate', 'precise', 'verification-PBE-v1'))

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

        protocol = copy.deepcopy(self.get_protocol(protocol))
        code = engines['relax']['code']

        pseudo_family_label = protocol.pop('pseudo_family')
        try:
            pseudo_family = orm.Group.collection.get(label=pseudo_family_label)
        except exceptions.NotExistent as exception:
            raise ValueError(
                f'required pseudo family `{pseudo_family_label}` is not installed. '
                'Please use `aiida-pseudo install pseudo-dojo` to install it.'
            ) from exception

        cutoff_stringency = protocol['cutoff_stringency']
        pseudo_type = pseudo_family.pseudo_type
        recommended_ecut_wfc, recommended_ecut_rho = pseudo_family.get_recommended_cutoffs(
            structure=structure, stringency=cutoff_stringency, unit='Eh'
        )
        if pseudo_type == 'pseudo.jthxml':
            # JTH XML are PAW; we need `pawecutdg`
            cutoff_parameters = {
                'ecut': np.ceil(recommended_ecut_wfc),
                'pawecutdg': np.ceil(recommended_ecut_rho),
            }
        else:
            # All others are NC; no need for `pawecutdg`
            cutoff_parameters = {'ecut': recommended_ecut_wfc}

        override = {
            'abinit': {
                'metadata': {'options': engines['relax']['options']},
                'pseudos': pseudo_family.get_pseudos(structure=structure),
                'parameters': cutoff_parameters,
            }
        }

        builder = self.process_class.get_builder()

        # Force threshold
        # NB we deal with this here because knowing threshold_f is necessary if the structure is a molecule.
        #   threshold_f will be used later in the generator to set the relax threshold
        #   (find "Continue force and stress thresholds" in this file.)
        if threshold_forces is not None:
            threshold_f = threshold_forces * units.eV_to_Ha / units.ang_to_bohr  # eV/Å -> Ha/Bohr
        else:
            threshold_f = 5.0e-5  # Abinit default value in Ha/Bohr

        # Deal with molecular case
        if structure.pbc == (False, False, False):
            # We assume the structure is a molecule which already has an appropriate vacuum applied
            # NB: the vacuum around the molecule must maintain the molecule's symmetries!
            warnings.warn(
                f'The input structure {structure} has no periodic boundary conditions, so we '
                'assume the structure is a molecule. The structure will be modified to have full PBC. We assume that '
                'the cell contains appropriate symmetry-conserving vacuum, and various tweaks for molecular systems '
                ' will be applied to the selected protocol!'
            )

            # Set pbc to [True, True, True]
            pbc_structure = structure.clone()
            pbc_structure.set_pbc([True, True, True])

            # Update protocol
            _ = protocol['base'].pop('kpoints_distance')  # Remove k-points distance; we will use gamma only
            _ = protocol['base']['abinit']['parameters'].pop(
                'tolvrs'
            )  # Remove tolvrs; we will use force tolerance for SCF
            # Set k-points to gamma-point
            protocol['base']['kpoints'] = [1, 1, 1]
            # protocol['base']['abinit']['parameters']['shiftk'] = [[0, 0, 0]]
            protocol['base']['abinit']['parameters']['nkpt'] = 1
            # Set a force tolerance for SCF convergence
            protocol['base']['abinit']['parameters']['toldff'] = threshold_f * 1.0e-1
            # Add a model macroscopic dielectric constant
            protocol['base']['abinit']['parameters']['diemac'] = 2.0

            inputs = generate_inputs(self.process_class._process_class, protocol, code, pbc_structure, override)
        elif False in structure.pbc:
            raise ValueError(
                f'The input structure has periodic boundary conditions {structure.pbc}, but partial '
                'periodic boundary conditions are not supported.'
            )
        else:
            inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)

        builder._merge(inputs)

        # RelaxType
        if relax_type == RelaxType.NONE:
            builder.abinit['parameters']['ionmov'] = 0  # do not move the ions, Abinit default
        elif relax_type == RelaxType.POSITIONS:
            # protocol defaults to POSITIONS
            pass
        elif relax_type == RelaxType.POSITIONS_CELL:
            builder.abinit['parameters']['optcell'] = 2  # fully optimize the cell geometry
            builder.abinit['parameters']['dilatmx'] = 1.15  # book additional mem. for p.w. basis exp.
            builder.abinit['parameters']['ecutsm'] = 0.5  # Ha, smearing on the energy cutoff
        elif relax_type == RelaxType.POSITIONS_VOLUME:
            builder.abinit['parameters']['optcell'] = 1  # optimize volume only
            builder.abinit['parameters']['dilatmx'] = 1.15  # book additional mem. for p.w. basis exp.
            builder.abinit['parameters']['ecutsm'] = 0.5  # Ha, smearing on the energy cutoff
        elif relax_type == RelaxType.POSITIONS_SHAPE:
            builder.abinit['parameters']['optcell'] = 3  # constant-volume optimization of cell geometry
            builder.abinit['parameters']['dilatmx'] = 1.05  # book additional mem. for p.w. basis exp.
            builder.abinit['parameters']['ecutsm'] = 0.5  # Ha, smearing on the energy cutoff
        else:
            raise ValueError(f'relax type `{relax_type.value}` is not supported')

        # SpinType
        if spin_type == SpinType.NONE:
            # protocol defaults to NONE
            pass
        elif spin_type == SpinType.COLLINEAR:
            if magnetization_per_site is None:
                magnetization_per_site = get_initial_magnetization(structure)
                warnings.warn(f'input magnetization per site was None, setting it to {magnetization_per_site}')
            magnetization_per_site = np.array(magnetization_per_site)

            sum_is_zero = np.isclose(sum(magnetization_per_site), 0.0)
            all_are_zero = np.all(np.isclose(magnetization_per_site, 0.0))
            non_zero_mags = magnetization_per_site[~np.isclose(magnetization_per_site, 0.0)]
            all_non_zero_pos = np.all(non_zero_mags > 0.0)
            all_non_zero_neg = np.all(non_zero_mags < 0.0)

            if all_are_zero:  # non-magnetic
                warnings.warn(
                    'all of the initial magnetizations per site are close to zero; doing a non-spin-polarized '
                    'calculation'
                )
            elif (sum_is_zero and not all_are_zero) or (
                not all_non_zero_pos and not all_non_zero_neg
            ):  # antiferromagnetic
                print('Detected antiferromagnetic!')
                builder.abinit['parameters']['nsppol'] = 1  # antiferromagnetic system
                builder.abinit['parameters']['nspden'] = 2  # scalar spin-magnetization in the z-axis
                builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
            elif not all_are_zero and (all_non_zero_pos or all_non_zero_neg):  # ferromagnetic
                print('Detected ferromagnetic!')
                builder.abinit['parameters']['nsppol'] = 2  # collinear spin-polarization
                builder.abinit['parameters']['nspden'] = 2  # scalar spin-magnetization in the z-axis
                builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
            else:
                raise ValueError(f'Initial magnetization {magnetization_per_site} is ambiguous')
        elif spin_type == SpinType.NON_COLLINEAR:
            if magnetization_per_site is None:
                magnetization_per_site = get_initial_magnetization(structure)
                warnings.warn(f'input magnetization per site was None, setting it to {magnetization_per_site}')
            # LATER: support vector magnetization_per_site
            builder.abinit['parameters']['nspinor'] = 2  # w.f. as spinors
            builder.abinit['parameters']['nsppol'] = 1  # spin-up and spin-down can't be disentangled
            builder.abinit['parameters']['nspden'] = 4  # vector magnetization
            builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
        elif spin_type == SpinType.SPIN_ORBIT:
            builder.abinit['parameters']['nspinor'] = 2  # w.f. as spinors
            builder.abinit['parameters']['kptopt'] = 4  # no time-reversal symmetry
        else:
            raise ValueError(f'spin type `{spin_type.value}` is not supported')

        # ElectronicType
        if electronic_type == ElectronicType.UNKNOWN:
            # protocol defaults to UNKNOWN, which is metallic with Gaussian smearing
            pass
        elif electronic_type == ElectronicType.METAL:
            builder.abinit['parameters']['occopt'] = 3  # Fermi-Dirac
        elif electronic_type == ElectronicType.INSULATOR:
            # LATER: Support magnetization with insulators
            if spin_type not in [SpinType.NONE, SpinType.SPIN_ORBIT]:
                raise ValueError(f'`spin_type` {spin_type.value} is not supported for insulating systems.')
            builder.abinit['parameters']['occopt'] = 1  # Fixed occupations, Abinit default
            builder.abinit['parameters']['fband'] = 0.125  # Abinit default
        else:
            raise ValueError(f'electronic type `{electronic_type.value}` is not supported')

        # Continue force and stress thresholds from above (see molecule treatment)
        builder.abinit['parameters']['tolmxf'] = threshold_f
        if threshold_stress is not None:
            threshold_s = threshold_stress * units.eV_to_Ha / units.ang_to_bohr**3  # eV/Å^3
            strfact = threshold_f / threshold_s
            builder.abinit['parameters']['strfact'] = strfact

        # previous workchain
        if reference_workchain is not None:
            try:
                previous_kpoints = reference_workchain.inputs.kpoints
            except exceptions.NotExistentAttributeError as not_existent_attr_error:
                query_builder = orm.QueryBuilder()
                query_builder.append(orm.WorkChainNode, tag='relax', filters={'id': reference_workchain.id})
                query_builder.append(
                    orm.WorkChainNode,
                    tag='base',
                    with_incoming='relax',
                )
                query_builder.append(
                    orm.CalcFunctionNode,
                    tag='calcfunc',
                    edge_filters={'label': 'create_kpoints_from_distance'},
                    with_incoming='base',
                )
                query_builder.append(orm.KpointsData, tag='kpoints', with_incoming='calcfunc')
                query_builder.order_by({orm.KpointsData: {'ctime': 'desc'}})
                query_builder_result = query_builder.all()
                if query_builder_result == []:
                    msg = f'Could not find KpointsData associated with {reference_workchain}'
                    raise ValueError(msg) from not_existent_attr_error
                previous_kpoints = query_builder_result[0][0]

            # ensure same k-points
            previous_kpoints_mesh, previous_kpoints_offset = previous_kpoints.get_kpoints_mesh()
            new_kpoints = orm.KpointsData()
            new_kpoints.set_cell_from_structure(structure)
            new_kpoints.set_kpoints_mesh(previous_kpoints_mesh, previous_kpoints_offset)
            builder.kpoints = new_kpoints

            # ensure same k-points shift
            shiftk = reference_workchain.inputs.abinit__parameters.get_dict().get('shiftk', None)
            if shiftk is not None:
                builder.abinit['parameters']['shiftk'] = shiftk

            nshiftk = reference_workchain.inputs.abinit__parameters.get_dict().get('nshiftk', None)
            if nshiftk is not None:
                builder.abinit['parameters']['nshiftk'] = nshiftk

        return builder


def generate_inputs(
    process_class: engine.Process,
    protocol: t.Dict,
    code: orm.Code,
    structure: StructureData,
    override: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Dict[str, t.Any]:
    """Generate the input parameters for the given workchain type for a given code and structure.

    The override argument can be used to pass a dictionary with values for specific inputs that should override the
    defaults. This dictionary should have the same nested structure as the final input dictionary would have for the
    workchain submission.

    :param process_class: process class, either calculation or workchain,
        i.e. ``AbinitCalculation`` or ``AbinitBaseWorkChain``
    :param protocol: the protocol based on which to choose input parameters
    :param code: the code or code name to use
    :param magnetism: the type of magnetisation to be used
    :param initial_mag: value for the initial magnetisation along the z axis.
    :param soc: whether or not to use spin-orbit coupling
    :param structure: the structure
    :param override: a dictionary to override specific inputs
    :return: input dictionary
    """

    from aiida.common.lang import type_check

    AbinitCalculation = plugins.CalculationFactory('abinit')  # noqa: N806
    AbinitBaseWorkChain = plugins.WorkflowFactory('abinit.base')  # noqa: N806

    type_check(structure, orm.StructureData)

    if process_class == AbinitCalculation:
        protocol = protocol['abinit']
        dictionary = generate_inputs_calculation(protocol, code, structure, override)
    elif process_class == AbinitBaseWorkChain:
        protocol = protocol['base']
        dictionary = generate_inputs_base(protocol, code, structure, override)
    else:
        raise NotImplementedError(f'process class {process_class} is not supported')

    return dictionary


def recursive_merge(left: t.Dict[str, t.Any], right: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Recursively merge two dictionaries into a single dictionary.

    :param left: first dictionary.
    :param right: second dictionary.
    :return: the recursively merged dictionary.
    """
    for key, value in left.items():
        if key in right:
            if isinstance(value, collections.abc.Mapping) and isinstance(right[key], collections.abc.Mapping):
                right[key] = recursive_merge(value, right[key])

    merged = left.copy()
    merged.update(right)

    return merged


def generate_inputs_base(
    protocol: t.Dict, code: orm.Code, structure: StructureData, override: t.Optional[t.Dict[str, t.Any]] = None
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `AbinitBaseWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['abinit'] = generate_inputs_calculation(protocol['abinit'], code, structure, override.get('abinit', {}))
    merged = recursive_merge(protocol, override or {})

    if isinstance(merged['abinit']['parameters'], dict):
        merged['abinit']['parameters'] = orm.Dict(dict=merged['abinit']['parameters'])

    if merged.get('kpoints_distance') is not None:
        dictionary = {'abinit': merged['abinit'], 'kpoints_distance': orm.Float(merged['kpoints_distance'])}
    elif merged.get('kpoints') is not None:
        kpoints = orm.KpointsData()
        kpoints.set_kpoints_mesh(merged['kpoints'])
        dictionary = {'abinit': merged['abinit'], 'kpoints': kpoints}
    else:
        raise ValueError('Neither `kpoints_distance` nor `kpoints` were specified as inputs')

    return dictionary


def generate_inputs_calculation(
    protocol: t.Dict, code: orm.Code, structure: StructureData, override: t.Optional[t.Dict[str, t.Any]] = None
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `AbinitCalculation` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    merged = recursive_merge(protocol, override or {})

    dictionary = {
        'code': code,
        'structure': structure,
        'pseudos': merged['pseudos'],
        'parameters': orm.Dict(dict=merged['parameters']),
        'metadata': merged.get('metadata', {}),
    }

    return dictionary


def get_initial_magnetization(structure: StructureData) -> t.List[float]:
    """Generate a guess for initial magnetization using a magnetic moment mapping.

    See the function for elements with known magnetization guesses. If a gues is not known, 0.01 is used
    for initialization.

    Includes values from `abipy` and `aiida-quantumespresso`.
    Co3+, Co4+, Mn3+, Mn4+ taken from `abipy`:
        https://github.com/abinit/abipy/blob/master/abipy/abio/inputs.py
    All others taken from `aiida-quantumespresso` (credit to Nicolas Mounet):
        "https://github.com/aiidateam/aiida-quantumespresso/blob/develop/
         aiida_quantumespresso/workflows/protocols/magnetization.yaml"
        * These values seem to be obtained by taking the maximum magnetic moment for each element with partially
            occupied d/f orbitals

    :param structure: structure
    :return: scalar initial magnetization for each Site in the structure
    """

    magmom_mapping = {
        'Ac': 5,
        'Ce': 5,
        'Co': 5,
        'Co3+': 0.6,
        'Co4+': 1,
        'Cr': 5,
        'Dy': 7,
        'Er': 7,
        'Eu': 7,
        'Fe': 5,
        'Gd': 5,
        'Hf': 5,
        'Ho': 7,
        'Ir': 5,
        'La': 5,
        'Lu': 5,
        'Mn': 5,
        'Mn3+': 4,
        'Mn4+': 3,
        'Mo': 5,
        'Nb': 5,
        'Nd': 7,
        'Ni': 5,
        'Np': 5,
        'Os': 5,
        'Pa': 5,
        'Pm': 7,
        'Pr': 7,
        'Pt': 5,
        'Pu': 7,
        'Re': 5,
        'Rh': 5,
        'Ru': 5,
        'Sc': 5,
        'Sm': 7,
        'Ta': 5,
        'Tb': 7,
        'Tc': 5,
        'Th': 5,
        'Ti': 5,
        'Tm': 7,
        'U': 5,
        'V': 5,
        'W': 5,
        'Y': 5,
        'Zr': 5,
    }

    magnetization = [magmom_mapping.get(site.kind_name, 0.01) for site in structure.sites]

    return magnetization
