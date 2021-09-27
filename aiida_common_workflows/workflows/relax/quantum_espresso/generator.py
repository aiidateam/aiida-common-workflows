# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Quantum ESPRESSO."""
from typing import Any, Dict, List, Tuple, Union

from aiida import engine
from aiida import orm
from aiida import plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('QuantumEspressoCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')


def create_magnetic_allotrope(structure, magnetization_per_site):
    """Create new structure with the correct magnetic kinds based on the magnetization per site

    :param structure: StructureData for which to create the new kinds.
    :param magnetization_per_site: List of magnetizations (defined as magnetic moments) for each site in the provided
        `structure`.
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    import string
    if structure.is_alloy:
        raise ValueError('Alloys are currently not supported.')

    allotrope = StructureData(cell=structure.cell, pbc=structure.pbc)
    allotrope_magnetic_moments = {}

    for element in structure.get_symbols_set():

        # Filter the sites and magnetic moments on the site element
        element_sites, element_magnetic_moments = zip(
            *[(site, magnetic_moment)
              for site, magnetic_moment in zip(structure.sites, magnetization_per_site)
              if site.kind_name.rstrip(string.digits) == element]
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
    """Input generator for the `QuantumEspressoCommonRelaxWorkChain`."""

    _engine_types = {
        'relax': {
            'code_plugin': 'quantumespresso.pw',
            'description': 'The code to perform the relaxation.'
        }
    }
    _relax_types = {
        relax_type: '...'
        for relax_type in RelaxType
        if relax_type not in (RelaxType.VOLUME, RelaxType.POSITIONS_VOLUME)
    }
    _spin_types = {
        SpinType.NONE: 'Treat the system without spin polarization.',
        SpinType.COLLINEAR: 'Treat the system with spin polarization.'
    }
    _electronic_types = {
        ElectronicType.METAL: 'Treat the system as a metal with smeared occupations.',
        ElectronicType.INSULATOR: 'Treat the system as an insulator with fixed occupations.'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        process_class = kwargs.get('process_class', None)

        if process_class is not None:
            self._default_protocol = process_class._process_class.get_default_protocol()
            self._protocols = process_class._process_class.get_available_protocols()

        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        self._default_protocol = self.process_class.get_default_protocol()
        self._protocols = self.process_class.get_available_protocols()

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: Union[RelaxType, str] = RelaxType.POSITIONS,
        electronic_type: Union[ElectronicType, str] = ElectronicType.METAL,
        spin_type: Union[SpinType, str] = SpinType.NONE,
        magnetization_per_site: Union[List[float], Tuple[float]] = None,
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
        # pylint: disable=too-many-locals,too-many-branches
        from aiida_quantumespresso.common import types
        from qe_tools import CONSTANTS

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

        builder = self.process_class._process_class.get_builder_from_protocol(  # pylint: disable=protected-access
            engines['relax']['code'],
            structure,
            protocol=protocol,
            overrides={
                'base': {
                    'pw': {
                        'metadata': {
                            'options': engines['relax']['options']
                        }
                    }
                },
                'base_final_scf': {
                    'pw': {
                        'metadata': {
                            'options': engines['relax']['options']
                        }
                    }
                },
            },
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
            relax = reference_workchain.get_outgoing(node_class=orm.WorkChainNode).one().node
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
        builder._process_class = self.process_class  # pylint: disable=protected-access

        return builder
