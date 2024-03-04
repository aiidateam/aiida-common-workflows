"""Tests for a minimal install of the package without any extra dependencies.

The unit tests in this module should be run against a minimal install of the package without any extra dependencies
installed. This guarantees that most of the code can be imported without any plugin packages being installed.
"""
import pytest
from aiida.common import exceptions
from aiida_common_workflows.plugins import WorkflowFactory, get_workflow_entry_point_names


@pytest.mark.minimal_install
def test_imports():
    """The following modules should be importable without any plugin packages installed."""
    import aiida_common_workflows.cli
    import aiida_common_workflows.common
    import aiida_common_workflows.generators
    import aiida_common_workflows.plugins
    import aiida_common_workflows.protocol
    import aiida_common_workflows.utils
    import aiida_common_workflows.workflows
    import aiida_common_workflows.workflows.dissociation
    import aiida_common_workflows.workflows.eos  # noqa: F401


@pytest.mark.minimal_install
@pytest.mark.parametrize('entry_point_name', get_workflow_entry_point_names('relax'))
def test_workflow_factory_relax(entry_point_name):
    """Test that trying to load common relax workflow implementations will raise if not installed.

    The exception message should provide the pip command to install the require plugin package.
    """
    plugin_name = entry_point_name.removeprefix('common_workflows.relax.')
    match = rf'.*plugin package is not installed.*`pip install aiida-common-workflows\[{plugin_name}\]`.*'
    with pytest.raises(exceptions.MissingEntryPointError, match=match):
        WorkflowFactory(entry_point_name)


@pytest.mark.minimal_install
@pytest.mark.parametrize('entry_point_name', get_workflow_entry_point_names('bands'))
def test_workflow_factory_bands(entry_point_name):
    """Test that trying to load common bands workflow implementations will raise if not installed.

    The exception message should provide the pip command to install the require plugin package.
    """
    plugin_name = entry_point_name.removeprefix('common_workflows.bands.')
    match = rf'.*plugin package is not installed.*`pip install aiida-common-workflows\[{plugin_name}\]`.*'
    with pytest.raises(exceptions.MissingEntryPointError, match=match):
        WorkflowFactory(entry_point_name)
