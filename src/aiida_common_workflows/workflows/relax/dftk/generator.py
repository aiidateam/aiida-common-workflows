"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Dftk."""
import collections
import copy
import pathlib
import typing as t
import warnings

from aiida import engine, orm, plugins
from aiida.common import exceptions
import numpy as np
from pymatgen.core import units
import yaml

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('DftkCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class DftkCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `DftkCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml')) as handle:
            self._protocols = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        # TODO: why is this being redefined? the super call should be enough, unless something is explicitly being overridden.
        # TODO: spin and relax after spin and relax implementation in aiida and DFTK
        # spec.inputs['spin_type'].valid_type = ChoiceType(tuple(SpinType))
        # spec.inputs['relax_type'].valid_type = ChoiceType([
        #     t for t in RelaxType if t not in (RelaxType.VOLUME, RelaxType.SHAPE, RelaxType.CELL)
        # ])
        spec.inputs['electronic_type'].valid_type = ChoiceType(
            (ElectronicType.METAL, ElectronicType.INSULATOR, ElectronicType.UNKNOWN, ElectronicType.AUTOMATIC)
        )
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('dftk')
        spec.inputs['protocol'].valid_type = ChoiceType(('fastest', 'fast', 'moderate', 'precise'))

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        # spin_type = kwargs['spin_type']
        # relax_type = kwargs['relax_type']
        electronic_type = kwargs['electronic_type']
        # magnetization_per_site = kwargs.get('magnetization_per_site', None)
        # threshold_forces = kwargs.get('threshold_forces', None)
        # threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        protocol = copy.deepcopy(self.get_protocol(protocol))
        code = engines['relax']['code']

        pseudo_family_label = protocol.pop('pseudo_family')
        try:
            # TODO: Fix deprecation warning "AiidaDeprecationWarning: `objects` property is deprecated, use `collection` instead. (this will be removed in v3)"
            pseudo_family = orm.Group.objects.get(label=pseudo_family_label)
        except exceptions.NotExistent as exception:
            raise ValueError(
                f'required pseudo family `{pseudo_family_label}` is not installed. '
                'Please use `aiida-pseudo install pseudo-dojo` to install it.'
            ) from exception

        cutoff_stringency = protocol['cutoff_stringency']
        recommended_ecut_wfc, recommended_ecut_rho = pseudo_family.get_recommended_cutoffs(
            structure=structure, stringency=cutoff_stringency, unit='Eh'
        )

        #TODO: pawecutdg after PAW implementation in DFTK
        # All are NC; no need for `pawecutdg`
        # cutoff_parameters = {'ecut': recommended_ecut_wfc}

        override = {
            'dftk': {
                'metadata': {
                    'options': engines['relax']['options']
                },
                'pseudos': pseudo_family.get_pseudos(structure=structure),
                'parameters': {
                    "basis_kwargs": {
                        "Ecut": recommended_ecut_wfc
                    }
                }
            }
        }

        builder = self.process_class.get_builder()


        

        # Force threshold
        # NB we deal with this here because knowing threshold_f is necessary if the structure is a molecule.
        #   threshold_f will be used later in the generator to set the relax threshold
        #   (find "Continue force and stress thresholds" in this file.)
        # if threshold_forces is not None:
        #     threshold_f = threshold_forces * units.eV_to_Ha / units.ang_to_bohr  # eV/Å -> Ha/Bohr
        # else:
        #     threshold_f = 5.0e-5  # Dftk default value in Ha/Bohr

        # Deal with molecular case
        # if structure.pbc == (False, False, False):
        #     # We assume the structure is a molecule which already has an appropriate vacuum applied
        #     # NB: the vacuum around the molecule must maintain the molecule's symmetries!
        #     warnings.warn(
        #         f'The input structure {structure} has no periodic boundary conditions, so we '
        #         'assume the structure is a molecule. The structure will be modified to have full PBC. We assume that '
        #         'the cell contains appropriate symmetry-conserving vacuum, and various tweaks for molecular systems '
        #         ' will be applied to the selected protocol!'
        #     )

        #     # Set pbc to [True, True, True]
        #     pbc_structure = structure.clone()
        #     pbc_structure.set_pbc([True, True, True])

        #     # Update protocol
        #     _ = protocol['base'].pop('kpoints_distance')  # Remove k-points distance; we will use gamma only
        #     _ = protocol['base']['dftk']['parameters'].pop(
        #         'tolvrs'
        #     )  # Remove tolvrs; we will use force tolerance for SCF
        #     # Set k-points to gamma-point
        #     protocol['base']['kpoints'] = [1, 1, 1]
        #     # protocol['base']['Dftk']['parameters']['shiftk'] = [[0, 0, 0]]
        #     #protocol['base']['Dftk']['parameters']['nkpt'] = 1
        #     # Set a force tolerance for SCF convergence
        #     #protocol['base']['Dftk']['parameters']['toldff'] = threshold_f * 1.0e-1
        #     # Add a model macroscopic dielectric constant
        #     #protocol['base']['Dftk']['parameters']['diemac'] = 2.0

        #     inputs = generate_inputs(self.process_class._process_class, protocol, code, pbc_structure, override)  # pylint: disable=protected-access
        # elif False in structure.pbc:
        #     raise ValueError(
        #         f'The input structure has periodic boundary conditions {structure.pbc}, but partial '
        #         'periodic boundary conditions are not supported.'
        #     )
        # else:
        #     inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access

        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)

        builder._update(inputs)  # pylint: disable=protected-access


        # TODO: relax_type after relax implementation in DFTK
        # TODO: spin_type after spin implementation in aiida


        # ElectronicType
        # Default: ElectronicType.METAL
        if electronic_type == ElectronicType.METAL:
            # Mazari-Vanderbilt (cold) smearing for metals
            builder.dftk['parameters']['model_kwargs']['smearing'] = {'$symbol': 'Smearing.MarzariVanderbilt'}
        elif electronic_type == ElectronicType.UNKNOWN:
            # Gaussian smearing for unknowns
            builder.dftk['parameters']['model_kwargs']['smearing'] = {'$symbol': 'Smearing.Gaussian'}
        elif electronic_type == ElectronicType.INSULATOR:
            # fixed occupations for insulators: remove temperature specified in protocol
            builder.dftk['parameters']['model_kwargs'].pop('temperature', None)
        else:
            raise ValueError(f'electronic type `{electronic_type.value}` is not supported')
            

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
                    with_incoming='base'
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
            builder.pop('kpoints_distance', None)

        return builder


def generate_inputs(
    process_class: engine.Process,
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    override: t.Dict[str, t.Any] = None
) -> t.Dict[str, t.Any]:
    """Generate the input parameters for the given workchain type for a given code and structure.

    The override argument can be used to pass a dictionary with values for specific inputs that should override the
    defaults. This dictionary should have the same nested structure as the final input dictionary would have for the
    workchain submission.

    :param process_class: process class, either calculation or workchain,
        i.e. ``DftkCalculation`` or ``DftkBaseWorkChain``
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

    DftkCalculation = plugins.CalculationFactory('dftk')  # pylint: disable=invalid-name
    DftkBaseWorkChain = plugins.WorkflowFactory('dftk.base')  # pylint: disable=invalid-name

    type_check(structure, orm.StructureData)

    if process_class == DftkCalculation:
        protocol = protocol['dftk']
        dictionary = generate_inputs_calculation(protocol, code, structure, override)
    elif process_class == DftkBaseWorkChain:
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
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    override: t.Dict[str, t.Any] = None
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `DftkBaseWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['dftk'] = generate_inputs_calculation(protocol['dftk'], code, structure, override.get('dftk', {}))
    merged = recursive_merge(protocol, override or {})

    if isinstance(merged['dftk']['parameters'], dict):
        merged['dftk']['parameters'] = orm.Dict(dict=merged['dftk']['parameters'])

    if merged.get('kpoints_distance') is not None:
        dictionary = {'dftk': merged['dftk'], 'kpoints_distance': orm.Float(merged['kpoints_distance'])}
    elif merged.get('kpoints') is not None:
        kpoints = orm.KpointsData()
        kpoints.set_kpoints_mesh(merged['kpoints'])
        dictionary = {'dftk': merged['dftk'], 'kpoints': kpoints}
    else:
        raise ValueError('Neither `kpoints_distance` nor `kpoints` were specified as inputs')

    return dictionary


def generate_inputs_calculation(
    protocol: t.Dict,
    code: orm.Code,
    structure: orm.StructureData,
    override: t.Dict[str, t.Any] = None
) -> t.Dict[str, t.Any]:
    """Generate the inputs for the `DftkCalculation` for a given code, structure and pseudo potential family.

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
