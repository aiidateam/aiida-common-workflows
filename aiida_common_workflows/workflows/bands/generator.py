# -*- coding: utf-8 -*-
"""Module with base input generator for the common bands workchains."""
import abc

from aiida import orm
from aiida import plugins

from aiida_common_workflows.common import ElectronicType, SpinType
from aiida_common_workflows.generators import ChoiceType, InputGenerator

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
        spec.input_namespace(
            'seekpath_parameters',
            help='Inputs for the seekpath to be passed to `get_explicit_kpoints_path`.',
        )
        spec.input(
            'seekpath_parameters.reference_distance',
            valid_type=float,
            default=0.025,
            help='Reference target distance between neighboring k-points along the path in units 1/Å.',
        )
        spec.input(
            'seekpath_parameters.symprec',
            valid_type=float,
            default=0.00001,
            help='The symmetry precision used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.angle_tolerance',
            valid_type=float,
            default=-1.0,
            help='The angle tollerance used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.threshold',
            valid_type=float,
            default=0.0000001,
            help='The treshold for determining edge cases. Meaning is different depending on bravais lattice.',
        )
        spec.input(
            'seekpath_parameters.with_time_reversal',
            valid_type=bool,
            default=True,
            help='If False, and the group has no inversion symmetry, additional lines are returned.',
        )
        spec.input(
            'bands_kpoints',
            valid_type=plugins.DataFactory('array.kpoints'),
            required=False,
            help='The full list of kpoints where to calculate bands, in (direct) coordinates of the reciprocal space.'
        )
        spec.input(
            'parent_folder',
            valid_type=orm.RemoteData,
            required=False,
            help='Parent folder that contains file to restart from (density matrix, wave-functions..). What is used '
            'is plugin dependent.'
        )
        spec.input(
            'structure',
            valid_type=plugins.DataFactory('structure'),
            help='The structure, it might be changed internally if seekpath is used.'
        )
        spec.input(
            'protocol',
            valid_type=ChoiceType(('fast', 'moderate', 'precise')),
            default='moderate',
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
            help='The initial magnetization of the system. Should be a list of floats, where each float represents the '
            'spin polarization in units of electrons, meaning the difference between spin up and spin down '
            'electrons, for the site. This also corresponds to the magnetization of the site in Bohr magnetons '
            '(μB).',
        )
        spec.input_namespace(
            'engines',
            help='Inputs for the quantum engines',
        )
        spec.input_namespace(
            'engines.bands',
            help='Inputs for the quantum engine performing the calculation of bands.',
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
            required=False,
            help='Options for the bands calculations jobs.',
        )
