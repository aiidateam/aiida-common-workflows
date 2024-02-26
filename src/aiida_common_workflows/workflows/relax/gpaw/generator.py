"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for GPAW."""
from __future__ import annotations

import pathlib
import typing as t

import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType

from ..generator import CommonRelaxInputGenerator

__all__ = ('GpawCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class GpawCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `GpawCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _engine_types: t.ClassVar = {
        'relax': {'code_plugin': 'ase.ase', 'description': 'The code to perform the relaxation.'}
    }
    _relax_types: t.ClassVar = {
        RelaxType.NONE: 'Do not perform relaxation.',
        RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
    }
    _spin_types: t.ClassVar = {
        SpinType.NONE: 'Treat the system without spin polarization.',
    }
    _electronic_types: t.ClassVar = {
        ElectronicType.METAL: 'Treat the system as a metal with smeared occupations.',
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the protocols configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml'), encoding='utf-8') as handle:
            self._protocols = yaml.safe_load(handle)

    def _construct_builder(  # noqa: PLR0913
        self,
        structure: StructureData,
        engines: t.Dict[str, t.Any],
        *,
        protocol: t.Optional[str] = None,
        relax_type: RelaxType | str = RelaxType.POSITIONS,
        electronic_type: ElectronicType | str = ElectronicType.METAL,
        spin_type: SpinType | str = SpinType.NONE,
        magnetization_per_site: t.List[float] | t.Tuple[float] | None = None,
        threshold_forces: t.Optional[float] = None,
        threshold_stress: t.Optional[float] = None,
        reference_workchain=None,
        **kwargs,
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            reference_workchain=reference_workchain,
            **kwargs,
        )

        if isinstance(electronic_type, str):
            electronic_type = ElectronicType(electronic_type)

        if isinstance(relax_type, str):
            relax_type = RelaxType(relax_type)

        if isinstance(spin_type, str):
            spin_type = SpinType(spin_type)

        protocol = self.get_protocol(protocol)

        parameters = protocol['parameters']
        parameters['atoms_getters'] = [
            'temperature',
            ['forces', {'apply_constraint': True}],
            ['masses', {}],
        ]
        if relax_type == RelaxType.NONE:
            parameters.pop('optimizer', {})

        kpoints = plugins.DataFactory('core.array.kpoints')()
        kpoints.set_cell_from_structure(structure)
        if reference_workchain:
            previous_kpoints = reference_workchain.inputs.kpoints
            kpoints.set_kpoints_mesh(
                previous_kpoints.base.attributes.get('mesh'), previous_kpoints.base.attributes.get('offset')
            )
        else:
            kpoints.set_kpoints_mesh_from_density(protocol['kpoint_distance'])

        builder = self.process_class.get_builder()
        builder.structure = structure
        builder.kpoints = kpoints
        builder.gpaw.code = engines['relax']['code']
        builder.gpaw.parameters = orm.Dict(dict=parameters)
        builder.gpaw.metadata.options = engines['relax']['options']

        return builder
