"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Abacus."""
from importlib import resources

import yaml
from aiida import engine, orm, plugins
from aiida_abacus.common import CONSTANTS

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('AbacusCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class AbacusCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the common relax workflow implementation of Abacus."""

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
        from .. import abacus

        with resources.open_text(abacus, 'protocol.yml') as handle:
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
        spec.inputs['relax_type'].valid_type = ChoiceType(tuple(RelaxType))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('abacus.abacus')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        from aiida_abacus.common import ElectronicType, RelaxType, SpinType, recursive_merge

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        electronic_type = kwargs['electronic_type']
        # magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        if isinstance(electronic_type, str):
            electronic_type = ElectronicType(electronic_type)
        else:
            electronic_type = ElectronicType(electronic_type.value)

        if isinstance(relax_type, str):
            relax_type = RelaxType(relax_type)
        else:
            relax_type = RelaxType(relax_type.value)

        if isinstance(spin_type, str):
            spin_type = SpinType(spin_type)
        else:
            spin_type = SpinType(spin_type.value)

        # if magnetization_per_site:
        #     kind_to_magnetization = set(zip([site.kind_name for site in structure.sites], magnetization_per_site))

        #     if len(structure.kinds) != len(kind_to_magnetization):
        #         structure, initial_magnetic_moments = create_magnetic_allotrope(structure, magnetization_per_site)
        #     else:
        #         initial_magnetic_moments = dict(kind_to_magnetization)
        # else:
        initial_magnetic_moments = None

        # Currently, the `aiida-abcus` workflows will expect one of the basic protocols to be passed to the
        # `get_builder_from_protocol()` method. Here, we switch to using the default protocol for the
        # `aiida-abacus` plugin and pass the local protocols as `overrides`.
        if protocol not in self.process_class._process_class.get_available_protocols():
            overrides = self._load_local_protocols()[protocol]
            protocol = self._default_protocol
        else:
            overrides = {}

        options_overrides = {
            'base': {'abacus': {'metadata': {'options': engines['relax']['options']}}},
            'base_final_scf': {'abacus': {'metadata': {'options': engines['relax']['options']}}},
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
            threshold = threshold_forces * CONSTANTS.bohr_to_ang.value / CONSTANTS.ry_to_ev.value
            parameters = builder.base['abacus']['parameters'].get_dict()
            parameters.setdefault('input', {})['force_thr'] = threshold
            builder.base['abacus']['parameters'] = orm.Dict(dict=parameters)

        if threshold_stress is not None:
            threshold = threshold_stress * CONSTANTS.ev_ang3_to_kbar.value  # Abacus uses kBar for stress threshold
            parameters = builder.base['abacus']['parameters'].get_dict()
            parameters.setdefault('input', {})['stress_thr'] = threshold
            builder.base['abacus']['parameters'] = orm.Dict(dict=parameters)

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

        # Currently the builder is set for the `AbacusRelaxWorkChain`, but we should return one for the wrapper
        # workchain
        # `AbacusCommonRelaxWorkChain` for which this input generator is built
        builder._process_class = self.process_class

        return builder
