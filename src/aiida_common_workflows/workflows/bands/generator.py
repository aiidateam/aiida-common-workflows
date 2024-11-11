"""Module with base input generator for the common bands workchains."""
import abc

from aiida import orm, plugins

from aiida_common_workflows.generators import InputGenerator

__all__ = ('CommonBandsInputGenerator',)


class CommonBandsInputGenerator(InputGenerator, metaclass=abc.ABCMeta):
    """Input generator for the common bands workflow.

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
            'bands_kpoints',
            valid_type=plugins.DataFactory('core.array.kpoints'),
            required=True,
            help='The full list of kpoints where to calculate bands, in (direct) coordinates of the reciprocal space.',
        )
        spec.input(
            'parent_folder',
            valid_type=orm.RemoteData,
            required=True,
            help='Parent folder that contains file to restart from (density matrix, wave-functions..). What is used '
            'is plugin dependent.',
        )
        spec.input_namespace(
            'engines',
            help='Inputs for the quantum engines',
        )
        spec.input_namespace(
            'engines.bands',
            help='Inputs for the quantum engine performing the bands calculation.',
        )
        spec.input(
            'engines.bands.code',
            valid_type=orm.Code,
            serializer=orm.load_code,
            help='The code instance to use for the bands calculation.',
        )
        spec.input(
            'engines.bands.options',
            valid_type=dict,
            non_db=True,
            required=False,
            help='Options for the bands calculation jobs.',
        )
