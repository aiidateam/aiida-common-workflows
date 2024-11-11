"""Module with base input generator for the common structure relax workchains."""
import abc

from aiida import orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, InputGenerator
from aiida_common_workflows.protocol import ProtocolRegistry

__all__ = ('CommonRelaxInputGenerator',)


class CommonRelaxInputGenerator(InputGenerator, ProtocolRegistry, metaclass=abc.ABCMeta):
    """Input generator for the common relax workflow.

    This class should be subclassed by implementations for specific quantum engines. After calling the super, they can
    modify the ports defined here in the base class as well as add additional custom ports.
    """

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.input(
            'structure',
            valid_type=plugins.DataFactory('core.structure'),
            help='The structure whose geometry should be optimized.',
        )
        spec.input(
            'protocol',
            valid_type=ChoiceType(('fast', 'moderate', 'precise')),
            default='moderate',
            non_db=True,
            help='The protocol to use for the automated input generation. This value indicates the level of precision '
            'of the results and computational cost that the input parameters will be selected for.',
        )
        spec.input(
            'spin_type',
            valid_type=SpinType,
            serializer=SpinType,
            default=SpinType.NONE,
            help='The type of spin polarization to be used.',
        )
        spec.input(
            'relax_type',
            valid_type=RelaxType,
            serializer=RelaxType,
            default=RelaxType.POSITIONS,
            help='The degrees of freedom during the geometry optimization process.',
        )
        spec.input(
            'electronic_type',
            valid_type=ElectronicType,
            serializer=ElectronicType,
            default=ElectronicType.METAL,
            help='The electronic character of the system.',
        )
        spec.input(
            'magnetization_per_site',
            valid_type=list,
            required=False,
            non_db=True,
            help='The initial magnetization of the system. Should be a list of floats, where each float represents the '
            'spin polarization in units of electrons, meaning the difference between spin up and spin down '
            'electrons, for the site. This also corresponds to the magnetization of the site in Bohr magnetons '
            '(μB).',
        )
        spec.input(
            'threshold_forces',
            valid_type=float,
            required=False,
            non_db=True,
            help='A real positive number indicating the target threshold for the forces in eV/Å. If not specified, '
            'the protocol specification will select an appropriate value.',
        )
        spec.input(
            'threshold_stress',
            valid_type=float,
            required=False,
            non_db=True,
            help='A real positive number indicating the target threshold for the stress in eV/Å^3. If not specified, '
            'the protocol specification will select an appropriate value.',
        )
        spec.input(
            'reference_workchain',
            valid_type=orm.WorkChainNode,
            non_db=True,
            required=False,
            help='The node of a previously completed process of the same type whose inputs should be taken into '
            'account when generating inputs. This is important for particular workflows where certain inputs have '
            'to be kept constant between successive iterations.',
        )
        spec.input_namespace(
            'engines',
            help='Inputs for the quantum engines',
        )
        spec.input_namespace(
            'engines.relax',
            help='Inputs for the quantum engine performing the geometry optimization.',
        )
        spec.input(
            'engines.relax.code',
            valid_type=orm.Code,
            serializer=orm.load_code,
            help='The code instance to use for the geometry optimization.',
        )
        spec.input(
            'engines.relax.options',
            valid_type=dict,
            required=False,
            non_db=True,
            help='Options for the geometry optimization calculation jobs.',
        )
