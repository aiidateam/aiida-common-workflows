"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for VASP."""
import pathlib
import typing as t

import yaml
from aiida import engine, plugins
from aiida.common.extendeddicts import AttributeDict

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('VaspCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class VaspCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `VaspCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols: t.ClassVar = {
        'fast': {'description': 'Fast and not so accurate.'},
        'moderate': {'description': 'Possibly a good compromise for quick checks.'},
        'precise': {'description': 'Decent level of accuracy with some exceptions.'},
        'verification-PBE-v1': {'description': 'Used for the ACWF study on unaries and oxides.'},
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        self._initialize_potential_mapping()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the protocols configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml'), encoding='utf-8') as handle:
            self._protocols = yaml.safe_load(handle)

    def _initialize_potential_mapping(self):
        """Initialize the potential mapping from the potential_mapping configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'potential_mapping.yml'), encoding='utf-8') as handle:
            self._potential_mapping = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(tuple(RelaxType))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('vasp.vasp')
        spec.inputs['protocol'].valid_type = ChoiceType(('fast', 'moderate', 'precise', 'verification-PBE-v1'))

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # Get the protocol that we want to use
        if protocol is None:
            protocol = self._default_protocol
        protocol = self.get_protocol(protocol)

        # Set the builder
        builder = self.process_class.get_builder()

        # Set code
        builder.code = engines['relax']['code']

        # Set structure
        builder.structure = structure

        # Set options
        builder.options = plugins.DataFactory('core.dict')(dict=engines['relax']['options'])

        # Set workchain related inputs, in this case, give more explicit output to report
        builder.verbose = plugins.DataFactory('core.bool')(True)

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

        # Set settings
        # Make sure the VASP parser is configured for the problem
        settings = AttributeDict()
        settings.update(
            {
                'parser_settings': {
                    'critical_notifications': {
                        'add_brmix': True,
                        'add_cnormn': False,
                        'add_denmp': True,
                        'add_dentet': True,
                        'add_edddav_zhegv': True,
                        'add_eddrmm_zhegv': True,
                        'add_edwav': True,
                        'add_fexcp': True,
                        'add_fock_acc': True,
                        'add_non_collinear': True,
                        'add_not_hermitian': True,
                        'add_pzstein': True,
                        'add_real_optlay': True,
                        'add_rhosyg': True,
                        'add_rspher': True,
                        'add_set_indpw_full': True,
                        'add_sgrcon': True,
                        'add_no_potimm': True,
                        'add_magmom': True,
                        'add_bandocc': True,
                    },
                    'add_energies': True,
                    'add_forces': True,
                    'add_stress': True,
                    'add_misc': {
                        'type': 'dict',
                        'quantities': [
                            'total_energies',
                            'maximum_stress',
                            'maximum_force',
                            'magnetization',
                            'notifications',
                            'run_status',
                            'run_stats',
                            'version',
                        ],
                        'link_name': 'misc',
                    },
                    'energy_type': ['energy_free', 'energy_no_entropy'],
                }
            }
        )
        builder.settings = plugins.DataFactory('core.dict')(dict=settings)

        # Configure the handlers
        handler_overrides = {
            'handler_unfinished_calc_ionic_alt': {'enabled': True},
            'handler_unfinished_calc_generic_alt': {'enabled': True},
            'handler_electronic_conv_alt': {'enabled': True},
            'handler_unfinished_calc_ionic': {'enabled': False},
            'handler_unfinished_calc_generic': {'enabled': False},
            'handler_electronic_conv': {'enabled': False},
        }
        builder.handler_overrides = plugins.DataFactory('core.dict')(dict=handler_overrides)

        # Set the parameters on the builder, put it in the code namespace to pass through
        # to the code inputs
        builder.parameters = plugins.DataFactory('core.dict')(dict={'incar': parameters_dict})

        # Set potentials and their mapping
        builder.potential_family = plugins.DataFactory('str')(protocol['potential_family'])
        builder.potential_mapping = plugins.DataFactory('core.dict')(
            dict=self._potential_mapping[protocol['potential_mapping']]
        )

        # Set the kpoint grid from the density in the protocol
        kpoints = plugins.DataFactory('core.array.kpoints')()
        kpoints.set_cell_from_structure(structure)
        if reference_workchain:
            previous_kpoints = reference_workchain.inputs.kpoints
            kpoints.set_kpoints_mesh(
                previous_kpoints.base.attributes.get('mesh'), previous_kpoints.base.attributes.get('offset')
            )
        else:
            kpoints.set_kpoints_mesh_from_density(protocol['kpoint_distance'])
        builder.kpoints = kpoints

        # Set the relax parameters
        relax = AttributeDict()
        if relax_type != RelaxType.NONE:
            # Perform relaxation of cell or positions
            relax.perform = plugins.DataFactory('core.bool')(True)
            relax.algo = plugins.DataFactory('str')(protocol['relax']['algo'])
            relax.steps = plugins.DataFactory('int')(protocol['relax']['steps'])
            if relax_type == RelaxType.POSITIONS:
                relax.positions = plugins.DataFactory('core.bool')(True)
                relax.shape = plugins.DataFactory('core.bool')(False)
                relax.volume = plugins.DataFactory('core.bool')(False)
            elif relax_type == RelaxType.CELL:
                relax.positions = plugins.DataFactory('core.bool')(False)
                relax.shape = plugins.DataFactory('core.bool')(True)
                relax.volume = plugins.DataFactory('core.bool')(True)
            elif relax_type == RelaxType.VOLUME:
                relax.positions = plugins.DataFactory('core.bool')(False)
                relax.shape = plugins.DataFactory('core.bool')(False)
                relax.volume = plugins.DataFactory('core.bool')(True)
            elif relax_type == RelaxType.SHAPE:
                relax.positions = plugins.DataFactory('core.bool')(False)
                relax.shape = plugins.DataFactory('core.bool')(True)
                relax.volume = plugins.DataFactory('core.bool')(False)
            elif relax_type == RelaxType.POSITIONS_CELL:
                relax.positions = plugins.DataFactory('core.bool')(True)
                relax.shape = plugins.DataFactory('core.bool')(True)
                relax.volume = plugins.DataFactory('core.bool')(True)
            elif relax_type == RelaxType.POSITIONS_SHAPE:
                relax.positions = plugins.DataFactory('core.bool')(True)
                relax.shape = plugins.DataFactory('core.bool')(True)
                relax.volume = plugins.DataFactory('core.bool')(False)
        else:
            # Do not perform any relaxation
            relax.perform = plugins.DataFactory('core.bool')(False)

        if threshold_forces is not None:
            threshold = threshold_forces
        else:
            threshold = protocol['relax']['threshold_forces']
        relax.force_cutoff = plugins.DataFactory('float')(threshold)

        if threshold_stress is not None:
            raise ValueError('Using a stress threshold is not directly available in VASP during relaxation.')

        builder.relax = relax

        return builder
