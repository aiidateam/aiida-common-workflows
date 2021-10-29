# -*- coding: utf-8 -*-
"""Base class for an input generator for a common workflow."""
import abc
import copy

from aiida import engine, orm
from ..protocol import ProtocolRegistry
from .spec import InputGeneratorSpec

__all__ = ('InputGenerator',)


class InputGenerator(ProtocolRegistry, metaclass=abc.ABCMeta):
    """Base class for an input generator for a common workflow."""

    _spec_cls: InputGeneratorSpec = InputGeneratorSpec

    @classmethod
    def spec(cls) -> InputGeneratorSpec:
        """Return the specification of the input generator."""
        try:
            return getattr(cls, '_spec')
        except AttributeError:
            try:
                cls._spec: InputGeneratorSpec = cls._spec_cls()
                cls.define(cls._spec)
                return cls._spec
            except Exception:
                del cls._spec
                raise

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError('invalid input generator `{}`: {}'.format(self.__class__.__name__, message))

        try:
            self.process_class = kwargs.pop('process_class')
        except KeyError:
            raise_invalid('required keyword argument `process_class` was not defined.')

    def get_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Return a process builder for the given inputs.

        What keyword arguments are accepted is determined by the input generator specification that is built in the
        ``define`` method of the specific subclass. This method will pre-process the keyword arguments against the spec,
        filling in any default values, before validating the complete dictionary of arguments against the spec. If the
        arguments are valid, they are stored under the ``parsed_kwargs`` attribute, otherwise an exception is raised.
        Specific subclass implementations should construct and return a builder from the parsed arguments stored under
        the ``parsed_kwargs`` attribute.
        """
        copied_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, orm.Data) and value.is_stored:
                copied_kwargs[key] = value
            else:
                copied_kwargs[key] = copy.deepcopy(value)

        processed_kwargs = self.spec().inputs.pre_process(copied_kwargs)
        serialized_kwargs = self.spec().inputs.serialize(processed_kwargs)
        validation_error = self.spec().inputs.validate(serialized_kwargs)

        if validation_error is not None:
            raise ValueError(validation_error)

        return self._construct_builder(**processed_kwargs)

    @abc.abstractmethod
    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
