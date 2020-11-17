# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for VASP."""
import pathlib
from typing import Any, Dict, List

import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.common.extendeddicts import AttributeDict

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('VaspRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class VaspRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `VASPRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'vasp.vasp', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell (shape and volume) fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell (shape and volume).',
        RelaxType.CELL: 'Relax only the cell (shape and volume).'
    }
    _spin_types = {SpinType.NONE: '....', SpinType.COLLINEAR: '....'}
    _electronic_types = {ElectronicType.METAL: '....', ElectronicType.INSULATOR: '....'}

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
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

        # Get the protocol that we want to use
        if protocol is None:
            protocol = self._default_protocol
        protocol = self.get_protocol(protocol)

        # Set the builder
        builder = self.process_class.get_builder()

        # Set code
        builder.code = orm.load_code(calc_engines['relax']['code'])

        # Set structure
        builder.structure = structure

        # Set options
        builder.options = plugins.DataFactory('dict')(dict=calc_engines['relax']['options'])

        # Set settings
        # Make sure we add forces and stress for the VASP parser
        settings = AttributeDict()
        settings.update({'parser_settings': {'add_forces': True, 'add_stress': True}})
        builder.settings = plugins.DataFactory('dict')(dict=settings)

        # Set workchain related inputs, in this case, give more explicit output to report
        builder.verbose = plugins.DataFactory('bool')(True)

        # Set parameters
        builder.parameters = plugins.DataFactory('dict')(dict=protocol['parameters'])

        # Set potentials and their mapping
        builder.potential_family = plugins.DataFactory('str')(protocol['potential_family'])
        builder.potential_mapping = plugins.DataFactory('dict')(
            dict=self._potential_mapping[protocol['potential_mapping']]
        )

        # Set the kpoint grid from the density in the protocol
        kpoints = plugins.DataFactory('array.kpoints')()
        kpoints.set_kpoints_mesh([1, 1, 1])
        kpoints.set_cell_from_structure(structure)
        rec_cell = kpoints.reciprocal_cell
        kpoints.set_kpoints_mesh(fetch_k_grid(rec_cell, protocol['kpoint_distance']))
        builder.kpoints = kpoints

        # Here we set the protocols fast, moderate and precise. These currently have no formal meaning.
        # After a while these will be set in the VASP workchain entrypoints using the convergence workchain etc.
        # However, for now we rely on defaults plane wave cutoffs and a set k-point density for the chosen protocol.
        relax = AttributeDict()
        relax.perform = plugins.DataFactory('bool')(True)
        relax.algo = plugins.DataFactory('str')(protocol['relax']['algo'])

        if relax_type == RelaxType.ATOMS:
            relax.positions = plugins.DataFactory('bool')(True)
            relax.shape = plugins.DataFactory('bool')(False)
            relax.volume = plugins.DataFactory('bool')(False)
        elif relax_type == RelaxType.CELL:
            relax.positions = plugins.DataFactory('bool')(False)
            relax.shape = plugins.DataFactory('bool')(True)
            relax.volume = plugins.DataFactory('bool')(True)
        elif relax_type == RelaxType.ATOMS_CELL:
            relax.positions = plugins.DataFactory('bool')(True)
            relax.shape = plugins.DataFactory('bool')(True)
            relax.volume = plugins.DataFactory('bool')(True)
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        if threshold_forces is not None:
            threshold = threshold_forces
        else:
            threshold = protocol['relax']['threshold_forces']
        relax.force_cutoff = plugins.DataFactory('float')(threshold)

        if threshold_stress is not None:
            raise ValueError('Using a stress threshold is not directly available in VASP during relaxation.')

        builder.relax = relax

        return builder


def fetch_k_grid(rec_cell, k_distance):
    """
    Suggest a sensible k-point sampling based on a supplied distance.

    :param rec_cell: A two dimensional ndarray of floats defining the reciprocal lattice with each vector as rows.
    :param k_distance: The k-point distance.

    :return kgrid: The k-point grid given the supplied `rec_cell` and `k_distance`

    This is usable for instance when performing
    plane wave cutoff convergence tests without a base k-point grid.

    """
    import numpy as np

    rec_cell_lenghts = np.linalg.norm(rec_cell, axis=1)
    kgrid = np.ceil(rec_cell_lenghts / np.float(k_distance))

    return kgrid.astype('int').tolist()
