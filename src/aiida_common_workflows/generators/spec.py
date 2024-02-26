"""Class to define the specification of an input generator."""
from __future__ import annotations

import typing as t

from aiida.engine import PortNamespace

from .ports import InputGeneratorPort

__all__ = ('InputGeneratorSpec',)


class InputGeneratorSpec:
    """Class to define the specification of an input generator."""

    PORT_NAMESPACE_TYPE = PortNamespace
    PORT_TYPE = InputGeneratorPort

    def __init__(self) -> None:
        self.inputs: PortNamespace = self.PORT_NAMESPACE_TYPE()

    @property
    def namespace_separator(self) -> str:
        """Return the character used to separate namespaces in a string."""
        return self.PORT_NAMESPACE_TYPE.NAMESPACE_SEPARATOR

    def _create_port(
        self, port_namespace: PortNamespace, port_class: InputGeneratorPort | PortNamespace, name: str, **kwargs: t.Any
    ) -> None:
        """Create a new port of a given class and name in a given namespace.

        :param port_namespace: namespace to which to add the port.
        :param port_class: class of the port to create.
        :param name: name of the port to create.
        :param kwargs: options to be passed to the port constructor.
        """
        namespace_parts = name.split(self.namespace_separator)
        port_name = namespace_parts.pop()

        if namespace_parts:
            namespace = self.namespace_separator.join(namespace_parts)
            port_namespace = port_namespace.create_port_namespace(namespace)

        port_namespace[port_name] = port_class(port_name, **kwargs)

    def input(self, name: str, **kwargs: t.Any) -> None:
        """Define an input port in the root port namespace.

        :param name: name of the port to create.
        :param kwargs: options to be passed to the port constructor.
        """
        self._create_port(self.inputs, self.PORT_TYPE, name, **kwargs)

    def input_namespace(self, name: str, **kwargs: t.Any) -> None:
        """Create a new port namespace in the root port namespace.

        Any intermediate port namespaces that need to be created for a nested namespace, will take constructor defaults.

        :param name: name of the new port namespace.
        :param kwargs: options to be passed to the port constructor.
        """
        self._create_port(self.inputs, self.PORT_NAMESPACE_TYPE, name, **kwargs)
