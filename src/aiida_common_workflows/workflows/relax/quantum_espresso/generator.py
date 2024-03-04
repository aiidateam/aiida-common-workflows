"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Quantum ESPRESSO."""
from importlib import resources

import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('QuantumEspressoCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


def create_magnetic_allotrope(structure, magnetization_per_site):
    """Create new structure with the correct magnetic kinds based on the magnetization per site

    :param structure: StructureData for which to create the new kinds.
    :param magnetization_per_site: List of magnetizations (defined as magnetic moments) for each site in the provided
        `structure`.
    """

    import string

    if structure.is_alloy:
        raise ValueError('Alloys are currently not supported.')

    allotrope = StructureData(cell=structure.cell, pbc=structure.pbc)
    allotrope_magnetic_moments = {}

    for element in structure.get_symbols_set():
        # Filter the sites and magnetic moments on the site element
        element_sites, element_magnetic_moments = zip(
            *[
                (site, magnetic_moment)
                for site, magnetic_moment in zip(structure.sites, magnetization_per_site)
                if site.kind_name.rstrip(string.digits) == element
            ]
        )
        magnetic_moment_set = set(element_magnetic_moments)
        if len(magnetic_moment_set) > 10:
            raise ValueError(
                'The requested magnetic configuration would require more than 10 different kind names for element '
                f'{element}. This is currently not supported to due the character limit for kind names in Quantum '
                'ESPRESSO.'
            )
        if len(magnetic_moment_set) == 1:
            magnetic_moment_kinds = {element_magnetic_moments[0]: element}
        else:
            magnetic_moment_kinds = {
                magmom: f'{element}{index}' for magmom, index in zip(magnetic_moment_set, string.digits)
            }
        for site, magnetic_moment in zip(element_sites, element_magnetic_moments):
            allotrope.append_atom(
                name=magnetic_moment_kinds[magnetic_moment],
                symbols=(element,),
                weights=(1.0,),
                position=site.position,
            )
        allotrope_magnetic_moments.update({kind_name: magmom for magmom, kind_name in magnetic_moment_kinds.items()})

    return (allotrope, allotrope_magnetic_moments)


class QuantumEspressoCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the common relax workflow implementation of Quantum ESPRESSO."""

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        process_class = kwargs.get('process_class', None)

        if process_class is not None:
            self._default_protocol = process_class._process_class.get_default_protocol()
            self._protocols = process_class._process_class.get_available_protocols()
            self._protocols.update({key: value['description'] for key, value in self._load_local_protocols().items()})

        super().__init__(*args, **kwargs)

    @staticmethod
    def _load_local_protocols():
        """Load the protocols defined in the ``aiida-common-workflows`` package."""
        from .. import quantum_espresso

        with resources.open_text(quantum_espresso, 'protocol.yml') as handle:
            protocol_dict = yaml.safe_load(handle)
        return protocol_dict

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['protocol'].valid_type = ChoiceType(('fast', 'moderate', 'precise', 'verification-PBE-v1'))
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            tuple(t for t in RelaxType if t not in (RelaxType.VOLUME, RelaxType.POSITIONS_VOLUME))
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('quantumespresso.pw')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        from aiida_quantumespresso.common import types
        from aiida_quantumespresso.workflows.protocols.utils import recursive_merge
        from qe_tools import CONSTANTS

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

        if isinstance(electronic_type, str):
            electronic_type = types.ElectronicType(electronic_type)
        else:
            electronic_type = types.ElectronicType(electronic_type.value)

        if isinstance(relax_type, str):
            relax_type = types.RelaxType(relax_type)
        else:
            relax_type = types.RelaxType(relax_type.value)

        if isinstance(spin_type, str):
            spin_type = types.SpinType(spin_type)
        else:
            spin_type = types.SpinType(spin_type.value)

        if magnetization_per_site:
            kind_to_magnetization = set(zip([site.kind_name for site in structure.sites], magnetization_per_site))

            if len(structure.kinds) != len(kind_to_magnetization):
                structure, initial_magnetic_moments = create_magnetic_allotrope(structure, magnetization_per_site)
            else:
                initial_magnetic_moments = dict(kind_to_magnetization)
        else:
            initial_magnetic_moments = None

        # Currently, the `aiida-quantumespresso` workflows will expect one of the basic protocols to be passed to the
        # `get_builder_from_protocol()` method. Here, we switch to using the default protocol for the
        # `aiida-quantumespresso` plugin and pass the local protocols as `overrides`.
        if protocol not in self.process_class._process_class.get_available_protocols():
            overrides = self._load_local_protocols()[protocol]
            protocol = self._default_protocol
        else:
            overrides = {}

        options_overrides = {
            'base': {'pw': {'metadata': {'options': engines['relax']['options']}}},
            'base_final_scf': {'pw': {'metadata': {'options': engines['relax']['options']}}},
        }
        overrides = recursive_merge(overrides, options_overrides)

        builder = self.process_class._process_class.get_builder_from_protocol(
            engines['relax']['code'],
            structure,
            protocol=protocol,
            overrides=overrides,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            initial_magnetic_moments=initial_magnetic_moments,
        )

        if threshold_forces is not None:
            threshold = threshold_forces * CONSTANTS.bohr_to_ang / CONSTANTS.ry_to_ev
            parameters = builder.base['pw']['parameters'].get_dict()
            parameters.setdefault('CONTROL', {})['forc_conv_thr'] = threshold
            builder.base['pw']['parameters'] = orm.Dict(dict=parameters)

        if threshold_stress is not None:
            threshold = threshold_stress * CONSTANTS.bohr_to_ang**3 / CONSTANTS.ry_to_ev
            parameters = builder.base['pw']['parameters'].get_dict()
            parameters.setdefault('CELL', {})['press_conv_thr'] = threshold
            builder.base['pw']['parameters'] = orm.Dict(dict=parameters)

        if reference_workchain:
            relax = reference_workchain.base.links.get_outgoing(node_class=orm.WorkChainNode).one().node
            base = sorted(relax.called, key=lambda x: x.ctime)[-1]
            calc = sorted(base.called, key=lambda x: x.ctime)[-1]
            kpoints = calc.inputs.kpoints

            builder.base.pop('kpoints_distance', None)
            builder.base.pop('kpoints_force_parity', None)
            builder.base_final_scf.pop('kpoints_distance', None)
            builder.base_final_scf.pop('kpoints_force_parity', None)

            builder.base['kpoints'] = kpoints
            builder.base_final_scf['kpoints'] = kpoints

        # Currently the builder is set for the `PwRelaxWorkChain`, but we should return one for the wrapper workchain
        # `QuantumEspressoCommonRelaxWorkChain` for which this input generator is built
        builder._process_class = self.process_class

        return builder
