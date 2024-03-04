"""Factories to load entry points."""
import typing as t

from aiida import plugins
from aiida.common import exceptions

if t.TYPE_CHECKING:
    from aiida.engine import WorkChain
    from importlib_metadata import EntryPoint

__all__ = ('WorkflowFactory',)


@t.overload
def WorkflowFactory(entry_point_name: str, load: t.Literal[True] = True) -> t.Union[t.Type['WorkChain'], t.Callable]:
    ...


@t.overload
def WorkflowFactory(entry_point_name: str, load: t.Literal[False]) -> 'EntryPoint':
    ...


def WorkflowFactory(entry_point_name: str, load: bool = True) -> t.Union['EntryPoint', t.Type['WorkChain'], t.Callable]:  # noqa: N802
    """Return the `WorkChain` sub class registered under the given entry point.

    :param entry_point_name: the entry point name.
    :param load: if True, load the matched entry point and return the loaded resource instead of the entry point itself.
    :return: sub class of :py:class:`~aiida.engine.processes.workchains.workchain.WorkChain` or a `workfunction`
    :raises aiida.common.MissingEntryPointError: entry point was not registered
    :raises aiida.common.MultipleEntryPointError: entry point could not be uniquely resolved
    :raises aiida.common.LoadingEntryPointError: entry point could not be loaded
    :raises aiida.common.InvalidEntryPointTypeError: if the type of the loaded entry point is invalid.
    """
    common_workflow_prefixes = ('common_workflows.relax.', 'common_workflows.bands.')
    try:
        return plugins.WorkflowFactory(entry_point_name, load)
    except exceptions.MissingEntryPointError as exception:
        for prefix in common_workflow_prefixes:
            if entry_point_name.startswith(prefix):
                plugin_name = entry_point_name.removeprefix(prefix)
                raise exceptions.MissingEntryPointError(
                    f'Could not load the entry point `{entry_point_name}`, probably because the plugin package is not '
                    f'installed. Please install it with `pip install aiida-common-workflows[{plugin_name}]`.'
                ) from exception
        else:  # noqa: PLW0120
            raise
