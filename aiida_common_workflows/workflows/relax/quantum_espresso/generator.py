# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Quantum ESPRESSO."""
import collections
import pathlib
from typing import Any, Dict, List
import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.common import exceptions
from aiida_sssp.groups import SsspFamily

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('QuantumEspressoRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class QuantumEspressoRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `QuantumEspressoRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'quantumespresso.pw', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
    }
    _spin_types = {SpinType.NONE: '....', SpinType.COLLINEAR: '....'}
    _electronic_types = {ElectronicType.METAL: '....', ElectronicType.INSULATOR: '....'}

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

        from qe_tools import CONSTANTS

        protocol = self.get_protocol(protocol)
        code = calc_engines['relax']['code']
        override = {'base': {'pw': {'metadata': {'options': calc_engines['relax']['options']}}}}

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access
        builder._update(inputs)  # pylint: disable=protected-access

        if relax_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        elif relax_type == RelaxType.ATOMS_CELL:
            relaxation_schema = 'vc-relax'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        builder.relaxation_scheme = orm.Str(relaxation_schema)

        if threshold_forces is not None:
            threshold = threshold_forces * CONSTANTS.bohr_to_ang / CONSTANTS.ry_to_ev
            parameters = builder.base.pw['parameters'].get_dict()
            parameters.setdefault('CONTROL', {})['forc_conv_thr'] = threshold
            builder.base.pw['parameters'] = orm.Dict(dict=parameters)

        if threshold_stress is not None:
            threshold = threshold_stress * CONSTANTS.bohr_to_ang**3 / CONSTANTS.ry_to_ev
            parameters = builder.base.pw['parameters'].get_dict()
            parameters.setdefault('CELL', {})['press_conv_thr'] = threshold
            builder.base.pw['parameters'] = orm.Dict(dict=parameters)

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
    structure: StructureData,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the input parameters for the given workchain type for a given code, structure and pseudo family.

    The override argument can be used to pass a dictionary with values for specific inputs that should override the
    defaults. This dictionary should have the same nested structure as the final input dictionary would have for the
    workchain submission. For example if one wanted to generate the inputs for a PwBandsWorkChain and override the
    ecutwfc parameter for the PwBaseWorkChain of the PwRelaxWorkChains, one would have to pass:

        override = {'relax': {'base': {'ecutwfc': 400}}}

    :param process_class: process class, either calculation or workchain, i.e. ``PwCalculation`` or ``PwBaseWorkChain``
    :param protocol: the protocol based on which to choose input parameters
    :param code: the code or code name to use
    :param structure: the structure
    :param override: a dictionary to override specific inputs
    :return: input dictionary
    """
    # pylint: disable=too-many-arguments,unused-argument
    from aiida.common.lang import type_check

    try:
        sssp_family = SsspFamily.objects.get(label=protocol['pseudo_family'])
    except exceptions.NotExistent:
        raise ValueError(
            'protocol `{}` requires the `{}` `SsspFamily` but could not be found.'.format(
                protocol['name'], protocol['pseudo_family']
            )
        )

    PwCalculation = plugins.CalculationFactory('quantumespresso.pw')  # pylint: disable=invalid-name
    PwBaseWorkChain = plugins.WorkflowFactory('quantumespresso.pw.base')  # pylint: disable=invalid-name
    PwRelaxWorkChain = plugins.WorkflowFactory('quantumespresso.pw.relax')  # pylint: disable=invalid-name

    type_check(structure, orm.StructureData)

    if not isinstance(code, orm.Code):
        try:
            code = orm.load_code(code)
        except (exceptions.MultipleObjectsError, exceptions.NotExistent) as exception:
            raise ValueError('could not load the code {}: {}'.format(code, exception))

    if process_class == PwCalculation:
        protocol = protocol['relax']['base']['pw']
        dictionary = generate_inputs_calculation(protocol, code, structure, sssp_family, override)
    elif process_class == PwBaseWorkChain:
        protocol = protocol['relax']['base']
        dictionary = generate_inputs_base(protocol, code, structure, sssp_family, override)
    elif process_class == PwRelaxWorkChain:
        protocol = protocol['relax']
        dictionary = generate_inputs_relax(protocol, code, structure, sssp_family, override)
    else:
        raise NotImplementedError('process class {} is not supported'.format(process_class))

    return dictionary


def generate_inputs_relax(
    protocol: Dict,
    code: orm.Code,
    structure: StructureData,
    sssp_family: SsspFamily,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `PwRelaxWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param sssp_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['base'] = generate_inputs_base(protocol['base'], code, structure, sssp_family, override.get('base', {}))
    merged = recursive_merge(protocol, override)

    # Remove inputs that should not be passed top-level
    merged['base']['pw'].pop('structure', None)

    dictionary = {
        'base': merged['base'],
        'structure': structure,
        'final_scf': orm.Bool(merged['final_scf']),
        'max_meta_convergence_iterations': orm.Int(merged['max_meta_convergence_iterations']),
        'meta_convergence': orm.Bool(merged['meta_convergence']),
        'volume_convergence': orm.Float(merged['volume_convergence']),
    }

    return dictionary


def generate_inputs_base(
    protocol: Dict,
    code: orm.Code,
    structure: StructureData,
    sssp_family: SsspFamily,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `PwBaseWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param sssp_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['pw'] = generate_inputs_calculation(protocol['pw'], code, structure, sssp_family, override.get('pw', {}))
    merged = recursive_merge(protocol, override or {})

    dictionary = {
        'pw': merged['pw'],
        'kpoints_distance': orm.Float(merged['kpoints_distance']),
        'kpoints_force_parity': orm.Bool(merged['kpoints_force_parity']),
    }

    return dictionary


def generate_inputs_calculation(
    protocol: Dict,
    code: orm.Code,
    structure: StructureData,
    sssp_family: SsspFamily,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `PwCalculation` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param sssp_family: the pseudo potential family.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    natoms = len(structure.sites)
    cutoffs = sssp_family.get_cutoffs(structure=structure)

    etot_conv_thr_per_atom = protocol.pop('etot_conv_thr_per_atom')
    conv_thr_per_atom = protocol.pop('conv_thr_per_atom')

    protocol['parameters']['CONTROL']['etot_conv_thr'] = natoms * etot_conv_thr_per_atom
    protocol['parameters']['ELECTRONS']['conv_thr'] = natoms * conv_thr_per_atom
    protocol['parameters']['SYSTEM']['ecutwfc'] = cutoffs[0]
    protocol['parameters']['SYSTEM']['ecutrho'] = cutoffs[1]

    merged = recursive_merge(protocol, override or {})

    dictionary = {
        'code': code,
        'structure': structure,
        'parameters': orm.Dict(dict=merged['parameters']),
        'pseudos': sssp_family.get_pseudos(structure=structure),
        'metadata': merged.get('metadata', {})
    }

    return dictionary
