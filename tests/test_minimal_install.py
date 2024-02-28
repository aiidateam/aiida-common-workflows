"""Tests for a minimal install of the package without any extra dependencies.

The unit tests in this module should be run against a minimal install of the package without any extra dependencies
installed. This guarantees that most of the code can be imported without any plugin packages being installed.
"""
import pytest


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
