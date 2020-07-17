# -*- coding: utf-8 -*-
# pylint: disable=abstract-method,arguments-differ,redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.workchain` module."""
import pytest

from aiida.plugins import entry_point, WorkflowFactory

from aiida_common_workflows.workflows.relax import RelaxInputsGenerator, CommonRelaxWorkChain


def get_entry_point_names():
    """Return the registered entry point names for the ``CommonRelaxWorkChain``."""
    group = 'aiida.workflows'
    entry_point_prefix = 'common_workflows.relax'
    return [name for name in entry_point.get_entry_point_names(group) if name.startswith(entry_point_prefix)]


@pytest.fixture(scope='function', params=get_entry_point_names())
def workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return WorkflowFactory(request.param)


def test_workchain_class(workchain):
    """Test that each registered common relax workchain can be imported and subclasses ``CommonRelaxWorkChain``."""
    assert issubclass(workchain, CommonRelaxWorkChain)


def test_get_inputs_generator(workchain):
    """Test that each registered common relax workchain defines the associated inputs generator."""
    assert isinstance(workchain.get_inputs_generator(), RelaxInputsGenerator)
