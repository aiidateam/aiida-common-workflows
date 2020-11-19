# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for ABINIT."""
import collections
import copy
import pathlib
from typing import Any, Dict, List
import warnings

import yaml
from pymatgen.core import units
import numpy as np

from aiida import engine, orm, plugins
from aiida.common import exceptions
from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('AbinitRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class AbinitRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `AbinitRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'abinit', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'Fix the atomic positions, cell volume, and cell shape.',
        RelaxType.ATOMS: 'Relax the atomic positions at fixed cell volume and shape.',
        RelaxType.ATOMS_CELL: 'Relax the atomic positions, cell volume, and cell shape.',
        RelaxType.ATOMS_VOLUME: 'Relax the atomic positions and cell volume at fixed cell shape.',
        RelaxType.ATOMS_SHAPE: 'Relax the atomic positions and cell shape at fixed cell volume.'
    }
    _spin_types = {
        SpinType.NONE: 'Do not enable any magnetization or spin-orbit coupling.',
        SpinType.COLLINEAR: 'Enable collinear magnetization. You must provide magnetization_per_site.',
        SpinType.NON_COLLINEAR: 'Enable non-collinear magnetization with spin-orbit coupling (spinor w.f.s).',
        SpinType.SPIN_ORBIT: 'Enable spin-orbit coupling (spinor w.f.s) without magnetization.'
    }
    _electronic_types = {
        ElectronicType.METAL: 'Treat the system as metallic by allowing occupations to change, ' \
            'using Fermi-Dirac smearing, and adding additional bands.',
        ElectronicType.INSULATOR: 'Treat the system as an insulator with fixed integer occupations.'
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
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
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

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access
        builder._update(inputs)  # pylint: disable=protected-access

        # RelaxType
        if relax_type == RelaxType.NONE:
            builder.abinit['parameters']['ionmov'] = 0  # do not move the ions, Abinit default
        elif relax_type == RelaxType.ATOMS:
            # protocol defaults to ATOMS
            pass
        elif relax_type == RelaxType.ATOMS_CELL:
            builder.abinit['parameters']['optcell'] = 2  # fully optimize the cell geometry
            builder.abinit['parameters']['dilatmx'] = 1.15  # book additional mem. for p.w. basis exp.
        elif relax_type == RelaxType.ATOMS_VOLUME:
            builder.abinit['parameters']['optcell'] = 1  # optimize volume only
            builder.abinit['parameters']['dilatmx'] = 1.15  # book additional mem. for p.w. basis exp.
        elif relax_type == RelaxType.ATOMS_SHAPE:
            builder.abinit['parameters']['optcell'] = 3  # constant-volume optimization of cell geometry
        else:
            raise ValueError('relax type `{}` is not supported'.format(relax_type.value))

        # SpinType
        if spin_type == SpinType.NONE:
            # protocol defaults to NONE
            pass
        elif spin_type == SpinType.COLLINEAR:
            if np.all(np.isclose(magnetization_per_site, 0)):
                warnings.warn('All initial magnetizations are 0, doing a non-spin-polarized calculation.')
            elif np.isclose(sum(magnetization_per_site), 0):  # antiferromagnetic
                builder.abinit['parameters']['nsppol'] = 1  # antiferromagnetic system
                builder.abinit['parameters']['nspden'] = 2  # scalar spin-magnetization in the z-axis
                builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
            else:  # ferromagnetic
                builder.abinit['parameters']['nsppol'] = 2  # collinear spin-polarization
                builder.abinit['parameters']['nspden'] = 2  # scalar spin-magnetization in the z-axis
                builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
        elif spin_type == SpinType.NON_COLLINEAR:
            # LATER: support vector magnetization_per_site
            builder.abinit['parameters']['nspinor'] = 2  # w.f. as spinors
            builder.abinit['parameters']['nsppol'] = 1  # spin-up and spin-down can't be disentangled
            builder.abinit['parameters']['nspden'] = 4  # vector magnetization
            builder.abinit['parameters']['spinat'] = [[0.0, 0.0, mag] for mag in magnetization_per_site]
        elif spin_type == SpinType.SPIN_ORBIT:
            if 'fr' not in protocol['pseudo_family']:
                raise ValueError('You must use the `stringent` protocol for SPIN_ORBIT calculations because '\
                    'it provides fully-relativistic pseudopotentials (`fr` is not in the protocol\'s '\
                    '`pseudo_family` entry).')
            builder.abinit['parameters']['nspinor'] = 2  # w.f. as spinors
        else:
            raise ValueError('spin type `{}` is not supported'.format(spin_type.value))

        # ElectronicType
        if electronic_type == ElectronicType.METAL:
            # protocal defaults to METAL
            pass
        elif electronic_type == ElectronicType.INSULATOR:
            # LATER: Support magnetization with insulators
            if spin_type not in [SpinType.NONE, SpinType.SPIN_ORBIT]:
                raise ValueError('`spin_type` {} is not supported for insulating systems.'.format(spin_type.value))
            builder.abinit['parameters']['occopt'] = 1  # fixed occupations, Abinit default
            builder.abinit['parameters']['fband'] = 0.125  # Abinit default
        else:
            raise ValueError('electronic type `{}` is not supported'.format(electronic_type.value))

        # force and stress thresholds
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

        # previous workchain
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

            # ensure same k-points
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
