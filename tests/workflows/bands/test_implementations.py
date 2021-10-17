# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso` module."""
# pylint: disable=redefined-outer-name
import pytest

from aiida import engine
from aiida import orm
from aiida import plugins

from aiida_common_workflows.common.types import ElectronicType, SpinType
from aiida_common_workflows.generators.ports import InputGeneratorPort
from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.bands.workchain import CommonBandsWorkChain


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('bands'))
def workchain(request) -> CommonBandsWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonBandsWorkChain``."""
    return plugins.WorkflowFactory(request.param)


def test_spec(workchain):
    """Test that the input specification of all implementations respects the common interface."""
    generator = workchain.get_input_generator()
    generator_spec = generator.spec()

    required_ports = {
        'structure': {
            'valid_type': plugins.DataFactory('structure')
        },
        'bands_kpoints': {
            'valid_type': plugins.DataFactory('array.kpoints')
        },
        'parent_folder': {
            'valid_type': orm.RemoteData
        },
        'protocol': {
            'valid_type': str
        },
        'spin_type': {
            'valid_type': SpinType
        },
        'electronic_type': {
            'valid_type': ElectronicType
        },
        'magnetization_per_site': {
            'valid_type': list
        },
        'engines': {},
        'seekpath_parameters': {}
    }

    for port_name, values in required_ports.items():
        assert isinstance(generator_spec.inputs.get_port(port_name), (InputGeneratorPort, engine.PortNamespace))

        if 'valid_type' in values:
            assert generator_spec.inputs.get_port(port_name).valid_type is values['valid_type']
