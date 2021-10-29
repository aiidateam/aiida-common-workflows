# -*- coding: utf-8 -*-
# pylint: disable=unsupported-membership-test,unsubscriptable-object
"""Module with base protocol registry."""
import copy
import typing

__all__ = ('ProtocolRegistry',)


class ProtocolRegistry:
    """Container for work chain input generation protocols."""

    _protocols = None
    _default_protocol = None

    def __init__(self):
        """Construct an instance of the protocol registry, validating the class attributes set by the sub class."""

        def raise_invalid(message):
            raise RuntimeError('invalid protocol registry `{}`: '.format(self.__class__.__name__) + message)

        if self._protocols is None:
            raise_invalid('does not define `_protocols`')

        for protocol in self._protocols.values():
            if not isinstance(protocol, dict):
                raise_invalid('protocol `{}` is not a dictionary'.format(protocol))

            if 'description' not in protocol:
                raise_invalid('protocol `{}` does not define the key `description`'.format(protocol))

        if self._default_protocol is None:
            raise_invalid('does not define `_default_protocol`')

        if self._default_protocol not in self._protocols:
            raise_invalid('default protocol `{}` is not a defined protocol'.format(self._default_protocol))

    def is_valid_protocol(self, name: str) -> bool:
        """Return whether the given protocol exists."""
        return name in self._protocols

    def get_protocol_names(self) -> typing.List[str]:
        """Return the list of protocol names."""
        return list(self._protocols.keys())

    def get_default_protocol_name(self) -> str:
        """Return the default protocol name."""
        return self._default_protocol

    def get_protocol(self, name: str) -> typing.Dict:
        """Return the protocol corresponding to the given name."""
        try:
            return copy.deepcopy(self._protocols[name])
        except KeyError as exception:
            raise ValueError('the protocol `{}` does not exist'.format(name)) from exception
