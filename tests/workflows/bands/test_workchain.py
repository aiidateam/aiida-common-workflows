"""Tests for the :mod:`aiida_common_workflows.workflows.bands.workchain` module."""
import pytest
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.bands import CommonBandsInputGenerator
from aiida_common_workflows.workflows.bands.workchain import CommonBandsWorkChain


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('bands'))
def workchain(request) -> CommonBandsWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonBandsWorkChain``."""
    return WorkflowFactory(request.param)


def test_workchain_class(workchain):
    """Test that each registered common bands workchain can be imported and subclasses ``CommonBandsWorkChain``."""
    assert issubclass(workchain, CommonBandsWorkChain)


def test_get_input_generator(workchain):
    """Test that each registered common bands workchain defines the associated input generator."""
    generator = workchain.get_input_generator()
    assert isinstance(generator, CommonBandsInputGenerator)
    assert issubclass(generator.process_class, CommonBandsWorkChain)
