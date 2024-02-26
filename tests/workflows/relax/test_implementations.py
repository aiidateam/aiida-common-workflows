"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso` module."""

import pytest
from aiida import engine, orm, plugins
from aiida_common_workflows.common.types import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators.ports import InputGeneratorPort
from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('relax'))
def workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return plugins.WorkflowFactory(request.param)


def test_spec(workchain):
    """Test that the input specification of all implementations respects the common interface."""
    generator = workchain.get_input_generator()
    generator_spec = generator.spec()

    required_ports = {
        'structure': {'valid_type': plugins.DataFactory('core.structure')},
        'protocol': {'valid_type': str},
        'spin_type': {'valid_type': SpinType},
        'relax_type': {'valid_type': RelaxType},
        'electronic_type': {'valid_type': ElectronicType},
        'magnetization_per_site': {'valid_type': list},
        'threshold_forces': {'valid_type': float},
        'threshold_stress': {'valid_type': float},
        'reference_workchain': {'valid_type': orm.WorkChainNode},
        'engines': {},
    }

    for port_name, values in required_ports.items():
        assert isinstance(generator_spec.inputs.get_port(port_name), (InputGeneratorPort, engine.PortNamespace))

        if 'valid_type' in values:
            assert generator_spec.inputs.get_port(port_name).valid_type is values['valid_type']
