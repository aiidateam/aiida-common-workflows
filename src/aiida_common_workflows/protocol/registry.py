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
            raise RuntimeError(f'invalid protocol registry `{self.__class__.__name__}`: ' + message)

        if self._protocols is None:
            raise_invalid('does not define `_protocols`')

        for protocol in self._protocols.values():
            if not isinstance(protocol, dict):
                raise_invalid(f'protocol `{protocol}` is not a dictionary')

            if 'description' not in protocol:
                raise_invalid(f'protocol `{protocol}` does not define the key `description`')

        if self._default_protocol is None:
            raise_invalid('does not define `_default_protocol`')

        if self._default_protocol not in self._protocols:
            raise_invalid(f'default protocol `{self._default_protocol}` is not a defined protocol')

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
            raise ValueError(f'the protocol `{name}` does not exist') from exception
