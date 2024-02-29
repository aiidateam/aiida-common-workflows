"""Module with utilities for working with the plugins provided by this plugin package."""
import typing

from aiida.plugins import entry_point

from .factories import WorkflowFactory

PACKAGE_PREFIX = 'common_workflows'

__all__ = ('get_workflow_entry_point_names', 'get_entry_point_name_from_class', 'load_workflow_entry_point')


def get_workflow_entry_point_names(workflow: str, leaf: bool = False) -> typing.List[str]:
    """Return the registered entry point names for the given common workflow.

    :param workflow: the name of the common workflow.
    :param leaf: if True, only return the leaf of the entry point name, i.e., the name of plugin that implements it.
    :return: list of entry points names.
    """
    prefix = f'{PACKAGE_PREFIX}.{workflow}.'
    entry_points_names = entry_point.get_entry_point_names('aiida.workflows')

    if not leaf:
        return [name for name in entry_points_names if name.startswith(prefix)]

    return [name[len(prefix) :] for name in entry_points_names if name.startswith(prefix)]


def get_entry_point_name_from_class(cls) -> str:
    """Return the full entry point string for the given class."""
    from aiida.plugins.entry_point import get_entry_point_from_class

    return get_entry_point_from_class(cls.__module__, cls.__name__)[1]


def load_workflow_entry_point(workflow: str, plugin_name: str):
    """Load the entry point for the given plugin implementation of a certain common workflow.

    :param workflow: the name of the common workflow.
    :param plugin_name: name of the plugin implementation.
    :return: the workchain class of the plugin implementation of the common workflow.
    """
    entry_point_name = f'{PACKAGE_PREFIX}.{workflow}.{plugin_name}'
    return WorkflowFactory(entry_point_name)
