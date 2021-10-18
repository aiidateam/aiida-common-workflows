# -*- coding: utf-8 -*-
"""Module with base input generator for the common structure relax workchains."""
import abc

from aiida import orm
from aiida import plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType, OccupationType, XcFunctionalType
from aiida_common_workflows.generators import ChoiceType, InputGenerator

__all__ = ('CommonRelaxInputGenerator',)


class CommonRelaxInputGenerator(InputGenerator, metaclass=abc.ABCMeta):
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
            valid_type=plugins.DataFactory('structure'),
            help='The structure whose geometry should be optimized.'
        )
        spec.input(
            'protocol',
            valid_type=ChoiceType(('fast', 'moderate', 'precise')),
            default='moderate',
            help='The protocol to use for the automated input generation. This value indicates the level of precision '
            'of the results and computational cost that the input parameters will be selected for.',
        )
        spec.input(
            'spin_orbit',
            valid_type=bool,
            default=False,
            help='Whether to apply spin-orbit coupling.',
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
            help='The initial magnetization of the system. Should be a list of floats, where each float represents the '
            'spin polarization in units of electrons, meaning the difference between spin up and spin down '
            'electrons, for the site. This also corresponds to the magnetization of the site in Bohr magnetons '
            '(μB).',
        )
        spec.input(
            'threshold_forces',
            valid_type=float,
            required=False,
            help='A real positive number indicating the target threshold for the forces in eV/Å. If not specified, '
            'the protocol specification will select an appropriate value.',
        )
        spec.input(
            'threshold_stress',
            valid_type=float,
            required=False,
            help='A real positive number indicating the target threshold for the stress in eV/Å^3. If not specified, '
            'the protocol specification will select an appropriate value.',
        )
        spec.input(
            'reference_workchain',
            valid_type=orm.WorkChainNode,
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
            help='Options for the geometry optimization calculation jobs.',
        )


class CommonDftRelaxInputGenerator(CommonRelaxInputGenerator, metaclass=abc.ABCMeta):
    """Input generator for the common relax workflow.

    .. note:: This class is a subclass of the ``CommonRelaxInputGenerator`` but defines some additional inputs that are
        common to a number of implementations.

    This class should be subclassed by implementations for specific quantum engines. After calling the super, they can
    modify the ports defined here in the base class as well as add additional custom ports.
    """

    @staticmethod
    def validate_kpoints_shift(value, _):
        """Validate the ``kpoints_shift`` input."""
        if not isinstance(value, list) or len(value) != 3 or any(not isinstance(element, float) for element in value):
            return f'The `kpoints_shift` argument should be a list of three floats, but got: `{value}`.'

    @staticmethod
    def validate_inputs(value, _):
        """Docs."""
        if value['spin_orbit'] is True and value['spin_type'] == SpinType.NONE:
            return '`spin_type` cannot be `SpinType.NONE` for `spin_orbit = True`.'

        smearing_broadening = value['smearing_broadening']
        occupation_type = value['occupation_type']

        if smearing_broadening is not None and occupation_type not in [
            OccupationType.FIXED, OccupationType.TETRAHEDRON
        ]:
            return f'cannot define `smearing_broadening` for `occupation_type = {occupation_type}.'

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs.validator = cls.validate_inputs
        spec.input(
            'occupation_type',
            valid_type=OccupationType,
            serializer=OccupationType,
            default=OccupationType.FIXED,
            help='The way to treat electronic occupations.',
        )
        spec.input(
            'smearing_broadening',
            valid_type=float,
            required=False,
            help='The broadening of the smearing in eV. Should only be specified if a smearing method is defined for'
            'the `occupation_type` input.',
        )
        spec.input(
            'xc_functional',
            valid_type=XcFunctionalType,
            serializer=XcFunctionalType,
            default=XcFunctionalType.PBE,
            help='The functional for the exchange-correlation to be used.',
        )
        spec.input(
            'kpoints_distance',
            valid_type=float,
            required=False,
            help='The desired minimum distance between k-points in reciprocal space in 1/Å. The implementation will'
            'guarantee that a k-point mesh is generated for which the distances between all adjacent k-points along '
            'each cell vector are at most this distance. It is therefore possible that the distance is smaller than '
            'requested along certain directions.',
        )
        spec.input(
            'kpoints_shift',
            valid_type=list,
            validator=cls.validate_kpoints_shift,
            required=False,
            help='Optional shift to apply to all k-points of the k-point mesh. Should be a list of three floats where '
            'each float is a number between 0 and 1.',
        )
