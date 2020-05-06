# -*- coding: utf-8 -*-
# pylint: disable=unsupported-membership-test,unsubscriptable-object
"""Module with base protocol registry."""

__all__ = ('ProtocolRegistry',)


class ProtocolRegistry:

    _protocols = None
    _default_protocol = None

    def __init__(self, *args, **kwargs):
        """Construct an instance of the protocol registry, validating the class attributes set by the sub class."""
        super().__init__(*args, **kwargs)

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

    def is_valid_protocol(self, name):
        return name in self._protocols

    def get_protocol_names(self):
        return list(self._protocols.keys())

    def get_default_protocol_name(self):
        return self._default_protocol

    def get_protocol(self, name):
        try:
            return self._protocols[name]
        except KeyError:
            raise ValueError('the protocol `{}` does not exist'.format(name))
