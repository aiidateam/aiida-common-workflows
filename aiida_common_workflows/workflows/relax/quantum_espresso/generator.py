# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Quantum ESPRESSO."""
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

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
    """Input generator for the common relax workflow implementation of Quantum ESPRESSO."""

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

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            tuple(t for t in RelaxType if t not in (RelaxType.VOLUME, RelaxType.POSITIONS_VOLUME))
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('quantumespresso.pw')
        spec.input(
            'clean_workdir',
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help='If `True`, work directories of all called calculation will be cleaned at the end of execution.'
        )

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        from aiida_quantumespresso.common import types
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
        clean_workdir = kwargs.get('clean_workdir')

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
        builder.clean_workdir = clean_workdir

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
