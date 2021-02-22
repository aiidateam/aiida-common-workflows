# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for VASP."""
import pathlib
from typing import Any, Dict, List

import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.common.extendeddicts import AttributeDict

from ..generator import RelaxInputGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('VaspRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')


class VaspRelaxInputGenerator(RelaxInputGenerator):
    """Input generator for the `VASPRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'vasp.vasp', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'Do not perform relaxation',
        RelaxType.ATOMS: 'Relax only the atomic positions.',
        RelaxType.CELL: 'Relax only the cell (shape and volume).',
        RelaxType.SHAPE: 'Relax only the cell shape.',
        RelaxType.VOLUME: 'Relax only the cell volume.',
        RelaxType.ATOMS_SHAPE: 'Relax both atomic positions and the cell shape.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell (shape and volume), meaning everything.'
    }
    _spin_types = {SpinType.NONE: 'Non spin polarized.', SpinType.COLLINEAR: 'Spin polarized (collinear).'}
    _electronic_types = {ElectronicType.METAL: 'Not used.', ElectronicType.INSULATOR: 'Not used.'}

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        self._initialize_potential_mapping()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the protocols configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocols.yml')) as handle:
            self._protocols = yaml.safe_load(handle)

    def _initialize_potential_mapping(self):
        """Initialize the potential mapping from the potential_mapping configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'potential_mapping.yml')) as handle:
            self._potential_mapping = yaml.safe_load(handle)

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
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
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
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
            **kwargs
        )

        # Get the protocol that we want to use
        if protocol is None:
            protocol = self._default_protocol
        protocol = self.get_protocol(protocol)

        # Set the builder
        builder = self.process_class.get_builder()

        # Set code
        builder.code = orm.load_code(engines['relax']['code'])

        # Set structure
        builder.structure = structure

        # Set options
        builder.options = plugins.DataFactory('dict')(dict=engines['relax']['options'])

        # Set settings
        # Make sure the VASP parser is configured for the problem
        settings = AttributeDict()
        settings.update({
            'parser_settings': {
                'add_energies': True,
                'add_forces': True,
                'add_stress': True,
                'add_misc': {
                    'type':
                    'dict',
                    'quantities': [
                        'total_energies', 'maximum_stress', 'maximum_force', 'magnetization', 'notifications',
                        'run_status', 'run_stats', 'version'
                    ],
                    'link_name':
                    'misc'
                }
            }
        })
        builder.settings = plugins.DataFactory('dict')(dict=settings)

        # Set workchain related inputs, in this case, give more explicit output to report
        builder.verbose = plugins.DataFactory('bool')(True)

        # Fetch initial parameters from the protocol file.
        # Here we set the protocols fast, moderate and precise. These currently have no formal meaning.
        # After a while these will be set in the VASP workchain entrypoints using the convergence workchain etc.
        # However, for now we rely on plane wave cutoffs and a set k-point density for the chosen protocol.
        # Please consult the protocols.yml file for details.
        parameters_dict = protocol['parameters']

        # Set spin related parameters
        if spin_type == SpinType.NONE:
            parameters_dict['ispin'] = 1
        elif spin_type == SpinType.COLLINEAR:
            parameters_dict['ispin'] = 2

        # Set the magnetization
        if magnetization_per_site is not None:
            parameters_dict['magmom'] = list(magnetization_per_site)

        # Set the parameters on the builder, put it in the code namespace to pass through
        # to the code inputs
        builder.parameters = plugins.DataFactory('dict')(dict={'incar': parameters_dict})

        # Set potentials and their mapping
        builder.potential_family = plugins.DataFactory('str')(protocol['potential_family'])
        builder.potential_mapping = plugins.DataFactory('dict')(
            dict=self._potential_mapping[protocol['potential_mapping']]
        )

        # Set the kpoint grid from the density in the protocol
        kpoints = plugins.DataFactory('array.kpoints')()
        kpoints.set_cell_from_structure(structure)
        if reference_workchain:
            previous_kpoints = reference_workchain.inputs.kpoints
            kpoints.set_kpoints_mesh(previous_kpoints.get_attribute('mesh'), previous_kpoints.get_attribute('offset'))
        else:
            kpoints.set_kpoints_mesh_from_density(protocol['kpoint_distance'])
        builder.kpoints = kpoints

        # Set the relax parameters
        relax = AttributeDict()
        if relax_type != RelaxType.NONE:
            # Perform relaxation of cell or positions
            relax.perform = plugins.DataFactory('bool')(True)
            relax.algo = plugins.DataFactory('str')(protocol['relax']['algo'])
            relax.steps = plugins.DataFactory('int')(protocol['relax']['steps'])
            if relax_type == RelaxType.ATOMS:
                relax.positions = plugins.DataFactory('bool')(True)
                relax.shape = plugins.DataFactory('bool')(False)
                relax.volume = plugins.DataFactory('bool')(False)
            elif relax_type == RelaxType.CELL:
                relax.positions = plugins.DataFactory('bool')(False)
                relax.shape = plugins.DataFactory('bool')(True)
                relax.volume = plugins.DataFactory('bool')(True)
            elif relax_type == RelaxType.VOLUME:
                relax.positions = plugins.DataFactory('bool')(False)
                relax.shape = plugins.DataFactory('bool')(False)
                relax.volume = plugins.DataFactory('bool')(True)
            elif relax_type == RelaxType.SHAPE:
                relax.positions = plugins.DataFactory('bool')(False)
                relax.shape = plugins.DataFactory('bool')(True)
                relax.volume = plugins.DataFactory('bool')(False)
            elif relax_type == RelaxType.ATOMS_CELL:
                relax.positions = plugins.DataFactory('bool')(True)
                relax.shape = plugins.DataFactory('bool')(True)
                relax.volume = plugins.DataFactory('bool')(True)
            elif relax_type == RelaxType.ATOMS_SHAPE:
                relax.positions = plugins.DataFactory('bool')(True)
                relax.shape = plugins.DataFactory('bool')(True)
                relax.volume = plugins.DataFactory('bool')(False)
        else:
            # Do not perform any relaxation
            relax.perform = plugins.DataFactory('bool')(False)

        if threshold_forces is not None:
            threshold = threshold_forces
        else:
            threshold = protocol['relax']['threshold_forces']
        relax.force_cutoff = plugins.DataFactory('float')(threshold)

        if threshold_stress is not None:
            raise ValueError('Using a stress threshold is not directly available in VASP during relaxation.')

        builder.relax = relax

        return builder
