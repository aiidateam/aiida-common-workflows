"""
Module with base input generator for the common post-processing workchains.
"""

import abc

from aiida import orm, plugins

from aiida_common_workflows.common.types import PostProcessQuantity
from aiida_common_workflows.generators import InputGenerator
from aiida_common_workflows.protocol import ProtocolRegistry

__all__ = ('CommonPostProcessInputGenerator',)


class CommonPostProcessInputGenerator(InputGenerator, ProtocolRegistry, metaclass=abc.ABCMeta):
    """Input generator for the common post-processing workflow.

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
            'parent_folder',
            valid_type=plugins.DataFactory('core.remote'),
            required=True,
            help='The parent folder containing the outputs of an SCF calculation.',
        )
        spec.input(
            'quantity',
            valid_type=PostProcessQuantity,
            serializer=PostProcessQuantity,
            required=True,
            help='The quantity to be post-processed.',
        )
        spec.input_namespace(
            'engines.pp',
            help='Inputs for the post-processing job.',
        )
        spec.input(
            'engines.pp.code',
            valid_type=orm.Code,
            serializer=orm.load_code,
            help='The code instance to use for post-processing.',
        )
        spec.input(
            'engines.pp.options',
            valid_type=dict,
            required=False,
            non_db=True,
            help='Options for post-processing jobs.',
        )
