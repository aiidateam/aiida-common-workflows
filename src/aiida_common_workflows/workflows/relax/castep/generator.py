"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for CASTEP"""
import collections
import copy
import pathlib
import typing as t
from math import pi

import yaml
from aiida import engine, orm, plugins
from aiida.common import exceptions

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

if t.TYPE_CHECKING:
    from aiida_castep.data.otfg import OTFGGroup

KNOWN_BUILTIN_FAMILIES = ('C19', 'NCP19', 'QC5', 'C17', 'C9')

__all__ = ('CastepCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class CastepCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `CastepCommonRelaxWorkChain`."""

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
        spec.inputs['protocol'].valid_type = ChoiceType(
            ('fast', 'moderate', 'precise', 'verification-PBE-v1', 'verification-PBE-v1-a0')
        )
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR, SpinType.NON_COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(tuple(RelaxType))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('castep.castep')

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
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # Taken from http://greif.geo.berkeley.edu/~driver/conversions.html
        # 1 eV/Angstrom3 = 160.21766208 GPa
        ev_to_gpa = 160.21766208

        # Because the subsequent generators may modify this dictionary and convert things
        # to AiiDA types, here we make a full copy of the original protocol
        protocol = copy.deepcopy(self.get_protocol(protocol))
        code = engines['relax']['code']

        override = {'base': {'calc': {'metadata': {'options': engines['relax']['options']}}}}
        param = {}
        if threshold_forces is not None:
            param['geom_force_tol'] = threshold_forces
        if threshold_stress is not None:
            param['geom_stress_tol'] = threshold_stress * ev_to_gpa

        # Assign relaxation types
        if relax_type == RelaxType.POSITIONS:
            param['fix_all_cell'] = True
        elif relax_type == RelaxType.POSITIONS_CELL:
            pass
        elif relax_type == RelaxType.POSITIONS_VOLUME:
            # Use cell constraints to tie the lattice parameters fix angles
            param['cell_constraints'] = ['1 1 1', '0 0 0']
        elif relax_type == RelaxType.POSITIONS_SHAPE:
            param['fix_vol'] = True
            # Use TPSD optimiser since LBFGS typically has slow convergence when
            # cell constraint is applied
            param['geom_method'] = 'tpsd'
        elif relax_type == RelaxType.NONE:
            param['task'] = 'singlepoint'
            # Activate the bypass mode
            override['relax_options'] = {'bypass': True}
        elif relax_type == RelaxType.CELL:
            param['fix_all_ions'] = True
        elif relax_type == RelaxType.SHAPE:
            param['fix_all_ions'] = True
            param['fix_vol'] = True
        elif relax_type == RelaxType.VOLUME:
            param['fix_all_ions'] = True
            param['cell_constraints'] = ['1 1 1', '0 0 0']
        else:
            raise ValueError(f'relaxation type `{relax_type.value}` is not supported')

        # Process the spin types
        if spin_type == SpinType.COLLINEAR:
            param['spin_polarized'] = True
        elif spin_type == SpinType.NON_COLLINEAR:
            param['spin_treatment'] = 'noncollinear'
            # Symmetry should be off, unless QUANTISATION_AXIS is supplied
            # that would be too advanced, here I just turn it off
            param.pop('symmetry_generate', None)
        # elif spin_type == SpinType.SPIN_ORBIT:
        #    param['spin_treatment'] = 'noncollinear'
        #    param['spin_orbit_coupling'] = True
        #    param.pop('symmetry_generate', None)
        elif spin_type == SpinType.NONE:
            param['spin_polarized'] = False
        else:
            raise ValueError(f'Spin type `{spin_type.value}` is not supported')

        # Process the initial magnetic moments
        if magnetization_per_site:
            # Support for colinear and non-colinear spins
            # for non-colinear spins a vector of length three is supplied and passed
            # to CASTEP
            if isinstance(magnetization_per_site[0], (float, int, list, tuple)):
                override['base']['calc']['settings'] = {'SPINS': magnetization_per_site}
            elif isinstance(magnetization_per_site[0], dict):
                raise ValueError('Dictionary style initialisation is not supported yet')
            else:
                raise ValueError(f'Unsupported `magnetization_per_site` format {magnetization_per_site[0]}')
        elif spin_type == SpinType.COLLINEAR:
            # Initialise with FM spin arrangement
            override['base']['calc']['settings'] = {'SPINS': [1.0] * len(structure.sites)}
        elif spin_type in (SpinType.NON_COLLINEAR, SpinType.SPIN_ORBIT):
            override['base']['calc']['settings'] = {'SPINS': [[1.0, 1.0, 1.0]] * len(structure.sites)}
            print('WARNING: initialising non-collinear calculation with spin pointing at (1., 1., 1.).')

        # Process electronic type
        # for plane-wave DFT density mixing is most efficient for both metal and insulators
        # these days. Here we stick to the default of CASTEP and do nothing here.
        # if electronic_type == ElectronicType.METAL:
        #    # Use fine kpoints grid for all metallic calculations
        # No need to do this since the default is spacing is sufficiently fine
        #    override['base']['kpoints_spacing'] = 0.03
        # elif electronic_type in (ElectronicType.INSULATOR, ElectronicType.AUTOMATIC):
        #    pass
        # else:
        #    raise ValueError('Unsupported `electronic_type` {}.'.format(electronic_type))

        # Raise the cut off energy for very soft pseudopotentials
        # this is because the small basis set will give rise to errors in EOS / variable volume
        # relaxation even with the "fine" option
        if 'cut_off_energy' not in protocol['relax']['base']['calc']['parameters']:
            with open(str(pathlib.Path(__file__).parent / 'soft_elements.yml'), encoding='utf-8') as fhandle:
                soft_elements = yaml.safe_load(fhandle)
            symbols = [kind.symbol for kind in structure.kinds]
            if all(sym in soft_elements for sym in symbols):
                param['cut_off_energy'] = 326  # eV, approximately 12 Ha
                param.pop('basis_precision', None)

        # Apply the overrides
        if param:
            override['base']['calc']['parameters'] = param

        # Ensure the pseudopotential family requested does exist
        pseudos_family = protocol['relax']['base']['pseudos_family']
        ensure_otfg_family(pseudos_family)

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)

        # Finally, apply the logic for previous workchain
        if reference_workchain:
            previous_energy = reference_workchain.outputs.total_energy
            query = orm.QueryBuilder()
            query.append(orm.Node, filters={'id': previous_energy.pk}, tag='eng')
            query.append(orm.CalcFunctionNode, with_outgoing='eng', tag='calcf')
            query.append(orm.Dict, with_outgoing='calcf', tag='output_parameters')
            query.append(orm.CalcJobNode, with_outgoing='output_parameters')
            previous_calcjob = query.one()[0]  # The previous calcjob that computed the energy

            # keep the previous kpoints mesh in the new workchain
            previous_kpoints = copy.deepcopy(previous_calcjob.inputs.kpoints)
            previous_kpoints.set_cell(structure.cell)
            inputs['calc']['kpoints'] = previous_kpoints
            inputs['base'].pop('kpoints_spacing', None)

        builder._merge(inputs)

        return builder


def recursive_merge(left: t.Dict[str, t.Any], right: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Recursively merge two dictionaries into a single dictionary.

    :param left: first dictionary.
    :param right: second dictionary.
    :return: the recursively merged dictionary.
    """
    for key, value in left.items():
        if key in right:
            if isinstance(value, collections.abc.Mapping) and isinstance(right[key], collections.abc.Mapping):
                # Here, the right dictionary is modified in-place and contains the merged items
                right[key] = recursive_merge(value, right[key])

    merged = left.copy()
    merged.update(right)

    return merged


def generate_inputs(
    process_class: engine.Process,
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    override: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Dict[str, t.Any]:
    """Generate the input parameters for the given workchain type for a given code, structure and pseudo family.

    The override argument can be used to pass a dictionary with values for specific inputs that should override the
    defaults. This dictionary should have the same nested structure as the final input dictionary would have for the
    workchain submission.

    :param process_class: process class, either calculation or workchain,
     i.e. ``CastepCalculation`` or ``CastepBaseWorkChain``
    :param protocol: the protocol based on which to choose input parameters
    :param code: the code or code name to use
    :param structure: the structure
    :param override: a dictionary to override specific inputs
    :return: input dictionary
    """
    from aiida.common.lang import type_check
    from aiida_castep.data.otfg import OTFGGroup

    family_name = protocol['relax']['base']['pseudos_family']
    if isinstance(family_name, orm.Str):
        family_name = family_name.value
    try:
        otfg_family = OTFGGroup.collection.get(label=family_name)
    except exceptions.NotExistent as exc:
        name = protocol['name']
        family = protocol['relax']['base']['pseudos_family']
        raise ValueError(f'protocol `{name}` requires the `{family}` `pseudos family` but could not be found.') from exc

    CastepCalculation = plugins.CalculationFactory('castep.castep')  # noqa: N806
    CastepBaseWorkChain = plugins.WorkflowFactory('castep.base')  # noqa: N806
    CastepRelaxWorkChain = plugins.WorkflowFactory('castep.relax')  # noqa: N806

    type_check(structure, orm.StructureData)

    if process_class == CastepCalculation:
        protocol = protocol['relax']['base']['calc']
        dictionary = generate_inputs_calculation(protocol, code, structure, otfg_family, override)
    elif process_class == CastepBaseWorkChain:
        protocol = protocol['relax']['base']
        dictionary = generate_inputs_base(protocol, code, structure, otfg_family, override)
    elif process_class == CastepRelaxWorkChain:
        protocol = protocol['relax']
        dictionary = generate_inputs_relax(protocol, code, structure, otfg_family, override)
    else:
        raise NotImplementedError(f'process class {process_class} is not supported')

    return dictionary


def generate_inputs_relax(
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: 'OTFGGroup',
    override: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `CastepCommonRelaxWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param otfg_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['base'] = generate_inputs_base(protocol['base'], code, structure, otfg_family, override.get('base', {}))
    merged = recursive_merge(protocol, override)

    # Remove inputs that should not be passed top-level
    merged['base'].pop('structure', None)

    calc = merged['base'].pop('calc')
    calc.pop('structure', None)

    # Here we move the 'calc' up from the 'base' this is how the relax workchain accepts inputs
    dictionary = {
        'base': merged['base'],
        'calc': calc,
        'structure': structure,
        'relax_options': orm.Dict(dict=merged['relax_options']),
    }

    return dictionary


def generate_inputs_base(
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: 'OTFGGroup',
    override: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `CastepBaseWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param otfg_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    merged = recursive_merge(protocol, override or {})

    # Here we pass the base namespace in
    calc_dictionary = generate_inputs_calculation(protocol, code, structure, otfg_family, override)
    # Structure and pseudo should be define at base level
    calc_dictionary.pop('pseudos')
    # Remove the kpoints input as here we use the spacing directly
    calc_dictionary.pop('kpoints', None)

    dictionary = {
        # Convert to CASTEP convention - no 2pi factor for real/reciprocal space conversion
        # This is the convention that CastepBaseWorkChain uses
        'kpoints_spacing': orm.Float(merged['kpoints_spacing'] / 2 / pi),
        'max_iterations': orm.Int(merged['max_iterations']),
        'pseudos_family': orm.Str(otfg_family.label),
        'calc': calc_dictionary,
        'ensure_gamma_centering': orm.Bool(merged.get('ensure_gamma_centering', False)),
    }

    return dictionary


def generate_inputs_calculation(
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: 'OTFGGroup',
    override: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `CastepCalculation` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param otfg_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    from aiida_castep.calculations.helper import CastepHelper
    from aiida_castep.data import get_pseudos_from_structure

    override = {} if not override else override.get('calc', {})
    # This merge perserves the merged `parameters` in the override
    merged_calc = recursive_merge(protocol['calc'], override)

    # Create KpointData for CastepCalculation, the kpoints_spacing passed is
    # already in the AiiDA convention, e.g. with 2pi factor built into it.
    kpoints = orm.KpointsData()
    kpoints.set_cell_from_structure(structure)
    kpoints.set_kpoints_mesh_from_density(protocol['kpoints_spacing'])

    # For bare calculation level, we need to make sure the dictionary is not "flat"
    param = merged_calc['parameters']

    # Remove incompatible options: cut_off_energy and basis_precisions can not be
    # both specified
    if 'cut_off_energy' in param:
        param.pop('basis_precision', None)

    helper = CastepHelper()
    param = helper.check_dict(param, auto_fix=True, allow_flat=True)

    dictionary = {
        'structure': structure,
        'kpoints': kpoints,
        'code': code,
        'parameters': orm.Dict(dict=param),
        'pseudos': get_pseudos_from_structure(structure, otfg_family.label),
        'metadata': merged_calc.get('metadata', {}),
    }
    # Add the settings input if present
    if 'settings' in merged_calc:
        dictionary['settings'] = orm.Dict(dict=merged_calc['settings'])

    return dictionary


def ensure_otfg_family(family_name, force_update=False):
    """
    Add common OTFG families if they do not exist
    NOTE: CASTEP also supports UPF families, but it is not enabled here, since no UPS based protocol
    has been implemented.
    """
    from aiida.common import NotExistent
    from aiida_castep.data.otfg import OTFGGroup, upload_otfg_family

    # Ensure family name is a str
    if isinstance(family_name, orm.Str):
        family_name = family_name.value
    try:
        OTFGGroup.collection.get(label=family_name)
    except NotExistent:
        has_family = False
    else:
        has_family = True

    # Check if it is builtin family
    if family_name in KNOWN_BUILTIN_FAMILIES:
        if not has_family:
            description = f"CASTEP built-in on-the-fly generated pseudos libraray '{family_name}'"
            upload_otfg_family([family_name], family_name, description, stop_if_existing=True)
        return

    # Not an known family - check if it in the additional settings list
    # Load configuration from the settings
    with open(str(pathlib.Path(__file__).parent / 'additional_otfg_families.yml'), encoding='utf-8') as handle:
        additional = yaml.safe_load(handle)

    if family_name in additional:
        if not has_family or force_update:
            description = f"Modified CASTEP built-in on-the-fly generated pseudos libraray '{family_name}'"
            upload_otfg_family(additional[family_name], family_name, description, stop_if_existing=False)
    elif not has_family:
        # No family found - and it is not recognized
        raise RuntimeError(f"Family name '{family_name}' is not recognized!")
