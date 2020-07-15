# -*- coding: utf-8 -*-
"""Module with base input generator for the common structure relaxation workchains."""
from abc import ABCMeta, abstractmethod
from enum import Enum

from aiida_common_workflows.protocol import ProtocolRegistry

__all__ = ('RelaxType', 'RelaxInputsGenerator')


class RelaxType(Enum):

    ATOMS = 'atoms'
    CELL = 'cell'
    ATOMS_CELL = 'atoms_cell'


class RelaxInputsGenerator(ProtocolRegistry, metaclass=ABCMeta):
    """Input generator for the common structure relaxation workchains.

    Subclasses should define the `_calc_types` and `_relax_types` class attributes, as well as the `get_builder` method.
    """

    _calc_types = None
    _relax_types = None

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
        super().__init__(*args, **kwargs)

        if self._calc_types is None:
            message = 'invalid inputs generator `{}`: does not define `_calc_types`'.format(self.__class__.__name__)
            raise RuntimeError(message)

        if self._relax_types is None:
            message = 'invalid inputs generator `{}`: does not define `_relax_types`'.format(self.__class__.__name__)
            raise RuntimeError(message)

        if any([not isinstance(relax_type, RelaxType) for relax_type in self._relax_types]):
            message = 'invalid inputs generator `{}`: `_relax_types`'.format(self.__class__.__name__)
            raise RuntimeError(message)

    @abstractmethod
    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        **kwargs
    ):
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
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
