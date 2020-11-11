# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for ABINIT."""
import collections
import copy
import pathlib
from typing import Any, Dict

import yaml
from pymatgen.core import units

from aiida import engine, orm, plugins
from aiida.common import exceptions
from aiida_common_workflows.workflows.relax.generator import (RelaxInputsGenerator, RelaxType, SpinType, ElectronicType)

__all__ = ('AbinitRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class AbinitRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `AbinitRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'abinit', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
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
        protocol,
        relaxation_type: RelaxType,
        threshold_forces: float = None,
        threshold_stress: float = None,
        previous_workchain=None,
        electronic_type=ElectronicType.METAL,
        spin_type=SpinType.NONE,
        magnetization_per_site=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements

        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            electronic_type, spin_type, magnetization_per_site, **kwargs
        )

        protocol = copy.deepcopy(self.get_protocol(protocol))
        code = calc_engines['relax']['code']
        pseudo_family = orm.Group.objects.get(label=protocol.pop('pseudo_family'))
        override = {
            'abinit': {
                'metadata': {
                    'options': calc_engines['relax']['options']
                },
                'pseudos': pseudo_family.get_pseudos(structure=structure)
            }
        }

        parameters = {}

        if kwargs:
            # param magnetism: Optional[str]
            # param initial_magnetization: Optional[List[float]]
            # param is_metallic: bool
            # param tsmear: Optional[float]
            # param do_soc: bool

            magnetism = kwargs.pop('magnetism', None)
            initial_magnetization = kwargs.pop('initial_magnetization', None)
            is_metallic = kwargs.pop('is_metallic', False)
            tsmear = kwargs.pop('tsmear', 0.01)  # Ha
            do_soc = kwargs.pop('do_soc', False)

            if magnetism is not None:
                if not initial_magnetization:
                    # this is a generic high spin initial state.
                    # consider using tools in abipy.
                    initial_magnetization = [[0., 0., 5.]] * len(structure)

                parameters['spinat'] = initial_magnetization

                if magnetism == 'ferro':
                    parameters['nsppol'] = 2
                elif magnetism == 'antiferro':
                    parameters['nsppol'] = 1
                    parameters['nspden'] = 2

            if is_metallic:
                parameters['occopt'] = 3
                parameters['fband'] = 2
                parameters['tsmear'] = tsmear

            if do_soc:
                parameters['nspinor'] = 2

        override['abinit']['parameters'] = parameters

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access
        builder._update(inputs)  # pylint: disable=protected-access

        if relaxation_type == RelaxType.ATOMS:
            optcell = 0
            ionmov = 22
        elif relaxation_type == RelaxType.ATOMS_CELL:
            optcell = 2
            ionmov = 22
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        builder.abinit['parameters']['optcell'] = optcell
        builder.abinit['parameters']['ionmov'] = ionmov

        if threshold_forces is not None:
            # The Abinit threshold_forces is in Ha/Bohr
            threshold_f = threshold_forces * units.eV_to_Ha / units.ang_to_bohr  # eV/Å
        else:
            # ABINIT default value. Set it explicitly in case it is changed.
            # How can we warn the user that we are using the tolxmf Abinit default value?
            threshold_f = 5.0e-5
        builder.abinit['parameters']['tolmxf'] = threshold_f
        if threshold_stress is not None:
            threshold_s = threshold_stress * units.eV_to_Ha / units.ang_to_bohr**3  # eV/Å^3
            strfact = threshold_f / threshold_s
            builder.abinit['parameters']['strfact'] = strfact

        if previous_workchain is not None:
            try:
                previous_kpoints = previous_workchain.inputs.kpoints
            except exceptions.NotExistentAttributeError:
                query_builder = orm.QueryBuilder()
                query_builder.append(orm.WorkChainNode, tag='relax', filters={'id': previous_workchain.id})
                query_builder.append(
                    orm.WorkChainNode,
                    tag='base',
                    with_incoming='relax',
                )
                query_builder.append(
                    orm.CalcFunctionNode,
                    tag='calcfunc',
                    edge_filters={'label': 'create_kpoints_from_distance'},
                    with_incoming='base'
                )
                query_builder.append(orm.KpointsData, tag='kpoints', with_incoming='calcfunc')
                query_builder.order_by({orm.KpointsData: {'ctime': 'desc'}})
                query_builder_result = query_builder.all()
                if query_builder_result == []:
                    raise ValueError(f'Could not find KpointsData associated with {previous_workchain}')
                previous_kpoints = query_builder_result[0][0]

            previous_kpoints_mesh, previous_kpoints_offset = previous_kpoints.get_kpoints_mesh()
            new_kpoints = orm.KpointsData()
            new_kpoints.set_cell_from_structure(structure)
            new_kpoints.set_kpoints_mesh(previous_kpoints_mesh, previous_kpoints_offset)
            builder.kpoints = new_kpoints

            # ensure same k-points shift
            shiftk = previous_workchain.inputs.abinit__parameters.get_dict().get('shiftk', None)
            if shiftk is not None:
                builder.abinit['parameters']['shiftk'] = shiftk

            nshiftk = previous_workchain.inputs.abinit__parameters.get_dict().get('nshiftk', None)
            if nshiftk is not None:
                builder.abinit['parameters']['nshiftk'] = nshiftk

        return builder


def generate_inputs(
    process_class: engine.Process,
    protocol: Dict,
    code: orm.Code,
    structure: StructureData,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
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
    # pylint: disable=too-many-arguments,unused-argument
    from aiida.common.lang import type_check

    AbinitCalculation = plugins.CalculationFactory('abinit')  # pylint: disable=invalid-name
    AbinitBaseWorkChain = plugins.WorkflowFactory('abinit.base')  # pylint: disable=invalid-name

    type_check(structure, orm.StructureData)

    if not isinstance(code, orm.Code):
        try:
            code = orm.load_code(code)
        except (exceptions.MultipleObjectsError, exceptions.NotExistent) as exception:
            raise ValueError('could not load the code {}: {}'.format(code, exception))

    if process_class == AbinitCalculation:
        protocol = protocol['abinit']
        dictionary = generate_inputs_calculation(protocol, code, structure, override)
    elif process_class == AbinitBaseWorkChain:
        protocol = protocol['base']
        dictionary = generate_inputs_base(protocol, code, structure, override)
    else:
        raise NotImplementedError('process class {} is not supported'.format(process_class))

    return dictionary


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


def generate_inputs_base(protocol: Dict,
                         code: orm.Code,
                         structure: StructureData,
                         override: Dict[str, Any] = None) -> Dict[str, Any]:
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

    dictionary = {'abinit': merged['abinit'], 'kpoints_distance': orm.Float(merged['kpoints_distance'])}

    return dictionary


def generate_inputs_calculation(
    protocol: Dict, code: orm.Code, structure: StructureData, override: Dict[str, Any] = None
) -> Dict[str, Any]:
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
        'metadata': merged.get('metadata', {})
    }

    return dictionary
