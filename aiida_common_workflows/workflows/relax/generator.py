# -*- coding: utf-8 -*-
"""Module with base input generator for the common structure relax workchains."""
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Tuple, Union

from aiida import engine
from aiida import plugins
from aiida_common_workflows.protocol import ProtocolRegistry

__all__ = ('ElectronicType', 'SpinType', 'RelaxType', 'RelaxInputsGenerator')

StructureData = plugins.DataFactory('structure')


class RelaxType(Enum):
    """Enumeration of known relax types."""

    NONE = 'none'
    ATOMS = 'atoms'
    VOLUME = 'volume'
    SHAPE = 'shape'
    CELL = 'cell'
    ATOMS_CELL = 'atoms_cell'
    ATOMS_VOLUME = 'atoms_volume'
    ATOMS_SHAPE = 'atoms_shape'


class SpinType(Enum):
    """Enumeration of known spin types."""

    NONE = 'none'
    COLLINEAR = 'collinear'
    NON_COLLINEAR = 'non_collinear'
    SPIN_ORBIT = 'spin_orbit'


class ElectronicType(Enum):
    """Enumeration of known electronic types."""

    AUTOMATIC = 'automatic'
    METAL = 'metal'
    INSULATOR = 'insulator'


class RelaxInputsGenerator(ProtocolRegistry, metaclass=ABCMeta):
    """Input generator for the common structure relax workchains.

    Subclasses should define the `_calc_types`, `_spin_types`, `_electronic_types` and `_relax_types` class attributes,
    as well as the `get_builder` method.
    """

    _spin_types = None
    _calc_types = None
    _relax_types = None
    _process_class = None
    _electronic_types = None

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""

        def raise_invalid(message):
            raise RuntimeError('invalid inputs generator `{}`: {}'.format(self.__class__.__name__, message))

        try:
            self._process_class = kwargs.pop('process_class')
        except KeyError:
            raise_invalid('required keyword argument `process_class` was not defined.')

        super().__init__(*args, **kwargs)

        if self._calc_types is None:
            raise_invalid('does not define `_calc_types`.')

        if self._relax_types is None:
            raise_invalid('does not define `_relax_types`.')

        if self._spin_types is None:
            raise_invalid('does not define `_spin_types`.')

        if self._electronic_types is None:
            raise_invalid('does not define `_electronic_types`.')

        if any(not isinstance(relax_type, RelaxType) for relax_type in self._relax_types):
            raise_invalid('`_relax_types` are not all an instance of `RelaxType`')

        if any(not isinstance(spin_type, SpinType) for spin_type in self._spin_types):
            raise_invalid('`_spin_types` are not all an instance of `SpinType`')

        if any(not isinstance(electronic_type, ElectronicType) for electronic_type in self._electronic_types):
            raise_invalid('`_electronic_types` are not all an instance of `ElectronicType`')

    @property
    def process_class(self):
        """Return the process class for which this instance is supposed to build the inputs."""
        return self._process_class

    @abstractmethod
    def get_builder(
        self,
        structure: StructureData,
        calc_engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: Union[List[float], Tuple[float]] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param calc_engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list/tuple with the initial spin polarization for each site. Float or integer
            in units of electrons. If not defined, the builder will automatically define the initial magnetization if
            and only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        if reference_workchain is not None:
            try:
                prev_wc_class = reference_workchain.process_class
                if prev_wc_class not in [self.process_class, self.process_class._process_class]:  # pylint: disable=protected-access
                    raise ValueError('The "reference_workchain" must be a node of {}'.format(self.process_class))
            except AttributeError:
                raise ValueError('The "reference_workchain" must be a node of {}'.format(self.process_class))

        if relax_type not in self._relax_types:
            raise ValueError('relax type `{}` is not supported'.format(relax_type))

        if electronic_type not in self._electronic_types:
            raise ValueError('electronic type `{}` is not supported'.format(electronic_type))

        if spin_type not in self._spin_types:
            raise ValueError('spin type `{}` is not supported'.format(spin_type))

        if magnetization_per_site is not None:
            if not isinstance(magnetization_per_site, (list, tuple)):
                raise ValueError('The `initial_magnetization` must be a list or a tuple')
            if len(magnetization_per_site) != len(structure.sites):
                raise ValueError('An initial magnetization must be defined for each site of `structure`')

    def get_calc_types(self):
        """Return the calculation types for this input generator."""
        return list(self._calc_types.keys())

    def get_calc_type_schema(self, key):
        """Return the schema of a particular calculation type for this input generator."""
        try:
            return self._calc_types[key]
        except KeyError:
            raise ValueError('the calculation type `{}` does not exist'.format(key))

    def get_relax_types(self):
        """Return the available relax types for this input generator."""
        return list(self._relax_types.keys())

    def get_spin_types(self):
        """Return the available spin types for this input generator."""
        return list(self._spin_types.keys())

    def get_electronic_types(self):
        """Return the available electronic types for this input generator."""
        return list(self._electronic_types.keys())
