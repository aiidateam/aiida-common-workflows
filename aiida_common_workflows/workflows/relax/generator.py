# -*- coding: utf-8 -*-
"""Module with base input generator for the common structure relaxation workchains."""
from abc import ABCMeta, abstractmethod
from enum import Enum

from aiida_common_workflows.protocol import ProtocolRegistry

__all__ = ('RelaxType', 'RelaxInputsGenerator')


class RelaxType(Enum):
    """Enumeration of known relax types."""

    ATOMS = 'atoms'
    CELL = 'cell'
    ATOMS_CELL = 'atoms_cell'


class RelaxInputsGenerator(ProtocolRegistry, metaclass=ABCMeta):
    """Input generator for the common structure relaxation workchains.

    Subclasses should define the `_calc_types` and `_relax_types` class attributes, as well as the `get_builder` method.
    """

    _calc_types = None
    _relax_types = None
    _process_class = None

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

        if any([not isinstance(relax_type, RelaxType) for relax_type in self._relax_types]):
            raise_invalid('`_relax_types` are not all an instance of `RelaxType`')

    @property
    def process_class(self):
        """Return the process class for which this instance is supposed to build the inputs."""
        return self._process_class

    @abstractmethod
    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        previous_workchain=None,
        **kwargs
    ):
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param previous_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """

    def get_calc_types(self):
        """Return the calculation types for this input generator."""
        return list(self._calc_types.keys())

    def get_calc_type_schema(self, key):
        """Return the schema of a particular calculation type for this input generator."""
        try:
            return self._calc_types[key]
        except KeyError:
            raise ValueError('the calculation type `{}` does not exist'.format(key))

    def get_relaxation_types(self):
        """Return the available relaxation types for this input generator."""
        return list(self._relax_types.keys())
