# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for CASTEP"""
import collections
import copy
import pathlib
from typing import Any, Dict, List
from math import pi
import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.common import exceptions
from aiida_castep.data import get_pseudos_from_structure
from aiida_castep.data.otfg import OTFGGroup

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType
# pylint: disable=import-outside-toplevel, too-many-branches, too-many-statements

__all__ = ('CastepRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')  # pylint: disable=invalid-name


class CastepRelaxInputGenerator(RelaxInputsGenerator):
    """Input generator for the `CastepRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'castep.castep', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.',
        RelaxType.ATOMS_SHAPE: 'Relax both atomic positions and the shape of the cell, keeping the volume fixed.',
        RelaxType.ATOMS_VOLUME: 'Relax both atomic positions and the volume of the cell, keeping the cell shape fixed.',
        RelaxType.NONE: 'Do not do any relaxation.'
    }
    _spin_types = {
        SpinType.NONE: 'No spin polarisation',
        SpinType.COLLINEAR: 'Collinear spin polarisation',
        SpinType.NON_COLLINEAR: 'Non-collinear spin. Symmetry is disabled by default.',
        # For now SOC requires special tabulated pseudopotentials (not the on-the-fly generated ones)
        # SpinType.SPIN_ORBIT: 'Non-collinear spin with spin-orbit coupling. Symmetry is disabled by default'
    }
    _electronic_types = {
        ElectronicType.METAL:
        'Allow variable occupation and use density mixing method with increased k-point density.',
        ElectronicType.INSULATOR:
        'Interally treated as metals, since density mixing is often more efficient for insulators.',
        ElectronicType.AUTOMATIC:
        'Interally treated as metals, since density mixing is often more efficient for insulators.'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml')) as handle:
            self._protocols = yaml.safe_load(handle)

    def get_builder(
        self,
        structure: StructureData,
        calc_engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        previous_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param calc_engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param previous_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            calc_engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            previous_workchain=previous_workchain,
            **kwargs
        )

        # Taken from http://greif.geo.berkeley.edu/~driver/conversions.html
        # 1 eV/Angstrom3 = 160.21766208 GPa
        ev_to_gpa = 160.21766208

        # Because the subsequent generators may modify this dictionary and convert things
        # to AiiDA types, here we make a full copy of the original protocol
        protocol = copy.deepcopy(self.get_protocol(protocol))
        code = calc_engines['relax']['code']

        override = {'base': {'calc': {'metadata': {'options': calc_engines['relax']['options']}}}}
        param = {}
        if threshold_forces is not None:
            param['geom_force_tol'] = threshold_forces
        if threshold_stress is not None:
            param['geom_stress_tol'] = threshold_stress * ev_to_gpa

        # Assign relaxation types
        if relax_type == RelaxType.ATOMS:
            param['fix_all_cell'] = True
        elif relax_type == RelaxType.ATOMS_CELL:
            pass
        elif relax_type == RelaxType.ATOMS_VOLUME:
            # Use cell constraints to tie the lattice parameters fix angles
            param['cell_constraints'] = ['1 1 1', '0 0 0']
        elif relax_type == RelaxType.ATOMS_SHAPE:
            param['fix_vol'] = True
        elif relax_type == RelaxType.NONE:
            param['task'] = 'singlepoint'
            # Activate the bypass mode
            override['relax_options'] = {'bypass': True}
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        # Process the spin types
        if spin_type == SpinType.COLLINEAR:
            param['spin_polarized'] = True
        elif spin_type == SpinType.NON_COLLINEAR:
            param['spin_treatment'] = 'noncollinear'
            # Symmetry should be off, unless QUANTISATION_AXIS is supplied
            # that would be too advanced, here I just turn it off
            param.pop('symmetry_generate', None)
        #elif spin_type == SpinType.SPIN_ORBIT:
        #    param['spin_treatment'] = 'noncollinear'
        #    param['spin_orbit_coupling'] = True
        #    param.pop('symmetry_generate', None)
        elif spin_type == SpinType.NONE:
            param['spin_polarized'] = False
        else:
            raise ValueError('Spin type `{}` is not supported'.format(spin_type.value))

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
                raise ValueError('Unsupported `magnetization_per_site` format {}'.format(magnetization_per_site[0]))
        elif spin_type == SpinType.COLLINEAR:
            # Initialise with FM spin arrangement
            override['base']['calc']['settings'] = {'SPINS': [1.0] * len(structure.sites)}
        elif spin_type in (SpinType.NON_COLLINEAR, SpinType.SPIN_ORBIT):
            override['base']['calc']['settings'] = {'SPINS': [[1.0, 1.0, 1.0]] * len(structure.sites)}
            print('WARNING: initialising non-collinear calculation with spin pointing at (1., 1., 1.).')

        # Process electronic type
        # for plane-wave DFT density mixing is most efficient for both metal and insulators
        # these days. Here we stick to the default of CASTEP and do nothing here.
        if electronic_type == ElectronicType.METAL:
            # Use fine kpoints grid for all metallic calculations
            override['base']['kpoints_spacing'] = 0.03
        elif electronic_type in (ElectronicType.INSULATOR, ElectronicType.AUTOMATIC):
            pass
        else:
            raise ValueError('Unsupported `electronic_type` {}.'.format(electronic_type))

        # Raise the cut off energy for very soft pseudopotentials
        # this is because the small basis set will give rise to errors in EOS / variable volume
        # relaxation even with the "fine" option
        with open(str(pathlib.Path(__file__).parent / 'soft_elements.yml')) as fhandle:
            soft_elements = yaml.safe_load(fhandle)
        symbols = [kind.symbol for kind in structure.kinds]
        if all([sym in soft_elements for sym in symbols]):
            param['cut_off_energy'] = 326  # eV, approximately 12 Ha

        # Apply the overrides
        if param:
            override['base']['calc']['parameters'] = param

        # Ensure the pseudopotential family requested does exist
        pseudos_family = protocol['relax']['base']['pseudos_family']
        ensure_otfg_family(pseudos_family)

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access

        # Finally, apply the logic for previous workchain
        if previous_workchain:
            previous_energy = previous_workchain.outputs.total_energy
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

        builder._update(inputs)  # pylint: disable=protected-access

        return builder


def recursive_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries into a single dictionary.

    :param left: first dictionary.
    :param right: second dictionary.
    :return: the recursively merged dictionary.
    """
    for key, value in left.items():
        if key in right:
            if isinstance(value, collections.Mapping) and isinstance(right[key], collections.Mapping):
                right[key] = recursive_merge(value, right[key])

    merged = left.copy()
    merged.update(right)

    return merged


def generate_inputs(
    process_class: engine.Process,
    protocol: Dict,
    code: orm.Code,
    structure: orm.StructureData,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
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
    # pylint: disable=too-many-arguments,unused-argument
    from aiida.common.lang import type_check

    family_name = protocol['relax']['base']['pseudos_family']
    if isinstance(family_name, orm.Str):
        family_name = family_name.value
    try:
        otfg_family = OTFGGroup.objects.get(label=family_name)
    except exceptions.NotExistent:
        raise ValueError(
            'protocol `{}` requires the `{}` `pseudos family` but could not be found.'.format(
                protocol['name'], protocol['relax']['base']['pseudos_family']
            )
        )

    CastepCalculation = plugins.CalculationFactory('castep.castep')  # pylint: disable=invalid-name
    CastepBaseWorkChain = plugins.WorkflowFactory('castep.base')  # pylint: disable=invalid-name
    CastepRelaxWorkChain = plugins.WorkflowFactory('castep.relax')  # pylint: disable=invalid-name

    type_check(structure, orm.StructureData)

    if not isinstance(code, orm.Code):
        try:
            code = orm.load_code(code)
        except (exceptions.MultipleObjectsError, exceptions.NotExistent) as exception:
            raise ValueError('could not load the code {}: {}'.format(code, exception))

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
        raise NotImplementedError('process class {} is not supported'.format(process_class))

    return dictionary


def generate_inputs_relax(
    protocol: Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: OTFGGroup,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `CastepRelaxWorkChain` for a given code, structure and pseudo potential family.

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

    # Here we move the 'calc' up from the 'base' this is how the relax workchain accepts inputs
    dictionary = {
        'base': merged['base'],
        'calc': calc,
        'structure': structure,
        'relax_options': orm.Dict(dict=merged['relax_options'])
    }

    return dictionary


def generate_inputs_base(
    protocol: Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: OTFGGroup,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
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
    calc_dictionary = generate_inputs_calculation(protocol, code, structure, otfg_family, override.get('calc', {}))
    # Structure and pseudo should be define at base level
    calc_dictionary.pop('structure')
    calc_dictionary.pop('pseudos')
    # Remove the kpoints input as here we use the spacing directly
    calc_dictionary.pop('kpoints', None)

    dictionary = {
        'kpoints_spacing': orm.Float(merged['kpoints_spacing']),
        'max_iterations': orm.Int(merged['max_iterations']),
        'pseudos_family': orm.Str(otfg_family.label),
        'calc': calc_dictionary
    }

    return dictionary


def generate_inputs_calculation(
    protocol: Dict,
    code: orm.Code,
    structure: orm.StructureData,
    otfg_family: OTFGGroup,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `CastepCalculation` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param otfg_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    from aiida_castep.calculations.helper import CastepHelper
    merged_calc = recursive_merge(protocol['calc'], override or {})

    kpoints = orm.KpointsData()
    kpoints.set_cell_from_structure(structure)
    kpoints.set_kpoints_mesh_from_density(protocol['kpoints_spacing'] * pi * 2)

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
        'metadata': merged_calc.get('metadata', {})
    }
    # Add the settings input if present
    if 'settings' in merged_calc:
        dictionary['settings'] = orm.Dict(dict=merged_calc['settings'])

    return dictionary


def ensure_otfg_family(family_name):
    """Add common OTFG families if they do not exist"""

    from aiida.common import NotExistent
    from aiida_castep.data.otfg import upload_otfg_family

    # Ensure family name is a str
    if isinstance(family_name, orm.Str):
        family_name = family_name.value

    try:
        OTFGGroup.objects.get(label=family_name)
    except NotExistent:
        description = f"CASTEP built-in on-the-fly generated pseudos libraray '{family_name}'"
        upload_otfg_family([family_name], family_name, description, stop_if_existing=True)
