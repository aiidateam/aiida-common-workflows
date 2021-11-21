# -*- coding: utf-8 -*-
"""Modules with resources to define specific port types for input generator specifications."""
import typing as t
from plumpy.ports import Port, PortValidationError, UNSPECIFIED, breadcrumbs_to_port
from aiida.engine import InputPort
from aiida.orm import Code

__all__ = ('ChoiceType', 'CodeType', 'InputGeneratorPort')


class CodeType:
    """Class that can be used for the ``valid_type`` of a ``InputPort`` that can define the required code plugin."""

    def __init__(self, entry_point=None):
        """Construct a new instance, storing the ``entry_point`` as an attribute."""
        self.entry_point = entry_point
        self.valid_type = Code


class ChoiceType:
    """Class that can be used for the ``valid_type`` of a ``InputPort`` that can define a sequence of valid choices."""

    def __init__(self, choices: t.Sequence[t.Any]):
        """Construct a new instance, storing the ``choices`` as an attribute and computing the tuple of valid types.

        The valid types are determined by taking the set of types of the given choices.

        :param choices: a sequence of valid choices for a port.
        """
        valid_types = tuple({type(choice) for choice in choices})
        self.choices: t.Sequence[t.Any] = choices
        self.valid_type: t.Tuple[t.Any] = valid_types if len(valid_types) > 1 else valid_types[0]


class InputGeneratorPort(InputPort):
    """Subclass of :class:`aiida.engine.InputPort` with support for choice types and value serializers."""

    code_entry_point = None
    choices = None

    def __init__(self, *args, valid_type_in_wc=None, valid_type=None, **kwargs) -> None:
        """Construct a new instance and process the ``valid_type`` keyword if it is an instance of ``ChoiceType``."""
        super().__init__(*args, **kwargs)
        self.valid_type = valid_type
        self.valid_type_in_wc = valid_type_in_wc

    @Port.valid_type.setter
    def valid_type(self, valid_type: t.Optional[t.Any]) -> None:
        """Set the valid value type for this port.

        :param valid_type: the value valid type.
        """
        if isinstance(valid_type, ChoiceType):
            self.choices = valid_type.choices
            valid_type = valid_type.valid_type

        if isinstance(valid_type, CodeType):
            self.code_entry_point = valid_type.entry_point
            valid_type = valid_type.valid_type

        self._valid_type = valid_type

    def validate(self, value: t.Any, breadcrumbs: t.Sequence[str] = ()) -> t.Optional[PortValidationError]:
        """Validate the value by calling the super followed by checking it against the choices if defined."""
        result = super().validate(value, breadcrumbs)

        if result is not None:
            return result

        if self.code_entry_point is not None and value.get_input_plugin_name() != self.code_entry_point:
            return f'invalid entry point `{value.get_input_plugin_name()}` for `Code{value}`.'

        if value is not UNSPECIFIED and self.choices is not None and value not in self.choices:
            choices = [str(value) for value in self.choices]
            message = f'`{value}` is not a valid choice. Valid choices are: {", ".join(choices)}'
            breadcrumbs = (breadcrumb for breadcrumb in (*breadcrumbs, self.name) if breadcrumb)
            return PortValidationError(message, breadcrumbs_to_port(breadcrumbs))

    @property
    def valid_type_in_wc(self) -> t.Optional[t.Type[t.Any]]:
        """Get the valid value type for this port if one is specified
        :return: the value value type
        """
        return self._valid_type_in_wc

    @valid_type_in_wc.setter
    def valid_type_in_wc(self, valid_type_in_wc: t.Optional[t.Type[t.Any]]) -> None:
        """Set the valid value type for this port
        :param valid_type: the value valid type
        """
        self._valid_type_in_wc = valid_type_in_wc
