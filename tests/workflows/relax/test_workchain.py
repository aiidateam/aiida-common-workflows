"""Tests for the :mod:`aiida_common_workflows.workflows.relax.workchain` module."""
import pytest
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.relax import CommonRelaxInputGenerator
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('relax'))
def workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return WorkflowFactory(request.param)


def test_workchain_class(workchain):
    """Test that each registered common relax workchain can be imported and subclasses ``CommonRelaxWorkChain``."""
    assert issubclass(workchain, CommonRelaxWorkChain)


def test_get_input_generator(workchain):
    """Test that each registered common relax workchain defines the associated input generator."""
    generator = workchain.get_input_generator()
    assert isinstance(generator, CommonRelaxInputGenerator)
    assert issubclass(generator.process_class, CommonRelaxWorkChain)
