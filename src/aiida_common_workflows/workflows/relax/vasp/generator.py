"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for VASP."""
import copy
import os
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
        spec.inputs['protocol'].valid_type = ChoiceType(
            ('fast', 'moderate', 'precise', 'verification-PBE-v1', 'custom')
        )

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        custom_protocol = kwargs.get('custom_protocol', None)
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # Get the protocol that we want to use
        if protocol is None:
            protocol = self._default_protocol

        if protocol == 'custom':
            if custom_protocol is None:
                raise ValueError(
                    'the `custom_protocol` input must be provided when the `protocol` input is set to `custom`.'
                )
            protocol = copy.deepcopy(custom_protocol)
        else:
            protocol = copy.deepcopy(self.get_protocol(protocol))

        # Set the builder
        builder = self.process_class.get_builder()

        # Set code
        builder.vasp.code = engines['relax']['code']

        # Set structure
        builder.structure = structure

        # Set options
        builder.vasp.calc.metadata.options = engines['relax']['options']

        # Set workchain related inputs, in this case, give more explicit output to report
        builder.verbose = True

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
                    'energy_types': ['energy_extrapolated', 'energy_free', 'energy_no_entropy'],
                    'critical_notification_errors': [
                        'brmix',
                        'edddav',
                        'eddwav',
                        'fexcp',
                        'fock_acc',
                        'non_collinear',
                        'not_hermitian',
                        'pzstein',
                        'real_optlay',
                        'rhosyg',
                        'rspher',
                        'set_indpw_full',
                        'sgrcon',
                        'no_potimm',
                        'magmom',
                        'bandocc',
                    ],
                    'energy_type': ['energy_free', 'energy_no_entropy'],
                }
            }
        )
        builder.vasp.settings = settings

        # Configure the handlers
        handler_overrides = {
            'handler_unfinished_calc_ionic_alt': {'enabled': True},
            'handler_unfinished_calc_generic_alt': {'enabled': True},
            'handler_electronic_conv_alt': {'enabled': True},
            'handler_unfinished_calc_ionic': {'enabled': False},
            'handler_unfinished_calc_generic': {'enabled': False},
            'handler_electronic_conv': {'enabled': False},
        }
        builder.vasp.handler_overrides = handler_overrides

        # Set the parameters on the builder, put it in the code namespace to pass through
        # to the code inputs
        builder.vasp.parameters = {'incar': parameters_dict}

        # Set potentials and their mapping
        if os.environ.get('PYTEST_CURRENT_TEST') is not None:
            builder.vasp._port_namespace['potential_family'].validator = None
        builder.vasp.potential_family = protocol['potential_family']
        builder.vasp.potential_mapping = self._potential_mapping[protocol['potential_mapping']]

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
        builder.vasp.kpoints = kpoints

        # Set the relax parameters
        relax_settings = AttributeDict()
        if relax_type != RelaxType.NONE:
            # Perform relaxation of cell or positions
            relax_settings.perform = True
            relax_settings.algo = protocol['relax']['algo']
            relax_settings.steps = protocol['relax']['steps']
            if relax_type == RelaxType.POSITIONS:
                relax_settings.positions = True
                relax_settings.shape = False
                relax_settings.volume = False
            elif relax_type == RelaxType.CELL:
                relax_settings.positions = False
                relax_settings.shape = True
                relax_settings.volume = True
            elif relax_type == RelaxType.VOLUME:
                relax_settings.positions = False
                relax_settings.shape = False
                relax_settings.volume = True
            elif relax_type == RelaxType.SHAPE:
                relax_settings.positions = False
                relax_settings.shape = True
                relax_settings.volume = False
            elif relax_type == RelaxType.POSITIONS_CELL:
                relax_settings.positions = True
                relax_settings.shape = True
                relax_settings.volume = True
            elif relax_type == RelaxType.POSITIONS_SHAPE:
                relax_settings.positions = True
                relax_settings.shape = True
                relax_settings.volume = False
        else:
            # Do not perform any relaxation
            relax_settings.perform = False
        if threshold_forces is not None:
            threshold = threshold_forces
        else:
            threshold = protocol['relax']['threshold_forces']
        relax_settings.force_cutoff = threshold

        if threshold_stress is not None:
            raise ValueError('Using a stress threshold is not directly available in VASP during relaxation.')

        builder.relax_settings = relax_settings

        return builder
