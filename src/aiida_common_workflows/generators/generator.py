"""Base class for an input generator for a common workflow."""
import abc
import copy

from aiida import engine, orm

from .spec import InputGeneratorSpec

__all__ = ('InputGenerator',)


def recursively_check_stored_nodes(obj):
    """Recursively create a deep copy of ``obj`` except for stored data nodes, which are kept as is.

    :param obj: the dictionary that should be recursively deep copied except for the stored data nodes.
    :return: a deepcopy of ``obj``.
    """
    if isinstance(obj, dict):
        return {k: recursively_check_stored_nodes(v) for k, v in obj.items()}
    if isinstance(obj, orm.Node):
        return obj
    return copy.deepcopy(obj)


class InputGenerator(metaclass=abc.ABCMeta):
    """Base class for an input generator for a common workflow."""

    _spec_cls: InputGeneratorSpec = InputGeneratorSpec

    @classmethod
    def spec(cls) -> InputGeneratorSpec:
        """Return the specification of the input generator."""
        try:
            return cls.__getattribute__(cls, '_spec')
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

        def raise_invalid(message):
            raise RuntimeError(f'invalid input generator `{self.__class__.__name__}`: {message}')

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
        # Create a deep copy of the input arguments because the ``pre_process`` step may alter them and
        # the originals need to be preserved in case they are passed to the ``get_builder`` method again, as
        # for example within a loop of a code-agnostic wrapping workchain like the ``EquationOfStateWorkChain``.
        # We cannot use ``copy.deepcopy`` directly, however, since it will create clones of any stored nodes that
        # are in the inputs. That's why we call `recursively_check_stored_nodes` which will recursively create a
        # deep copy of all inputs except for the stored nodes.
        copied_kwargs = recursively_check_stored_nodes(kwargs)

        processed_kwargs = self.spec().inputs.pre_process(copied_kwargs)
        serialized_kwargs = self.spec().inputs.serialize(processed_kwargs)
        validation_error = self.spec().inputs.validate(serialized_kwargs)

        if validation_error is not None:
            raise ValueError(validation_error)

        return self._construct_builder(**serialized_kwargs)

    @abc.abstractmethod
    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
