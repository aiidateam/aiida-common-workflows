# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
import pytest

from aiida_common_workflows.protocol import ProtocolRegistry
from aiida_common_workflows.workflows.relax import RelaxInputsGenerator, RelaxType


@pytest.fixture
def protocol_registry():

    class SubProtocolRegistry(ProtocolRegistry):

        _protocols = {'efficiency': {'description': 'description'}, 'precision': {'description': 'description'}}
        _default_protocol = 'efficiency'

    return SubProtocolRegistry


@pytest.fixture
def inputs_generator(protocol_registry):

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):

        _calc_types = {'relax': {'code_plugin': 'entry.point', 'description': 'test'}}

        _relax_types = {
            RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
            RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
        }

        def get_builder(self):
            pass

    return InputsGenerator()


def test_validation(protocol_registry):
    """Test the validation of subclasses of `ProtocolRegistry`."""

    # pylint: disable=abstract-class-instantiated,function-redefined

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):

        _calc_types = None
        _relax_types = None

    with pytest.raises(TypeError):
        InputsGenerator()

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):

        _calc_types = {'relax': {}}
        _relax_types = None

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator()

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):

        _calc_types = None
        _relax_types = {RelaxType.ATOMS: 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator()

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):

        _calc_types = {'relax': {}}
        _relax_types = {'invalid-type': 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator()


def test_get_calc_types(inputs_generator):
    """Test `RelaxInputsGenerator.get_calc_types`."""
    assert inputs_generator.get_calc_types() == ['relax']


def test_get_calc_type_schema(inputs_generator):
    """Test `RelaxInputsGenerator.get_calc_type_schema`."""
    assert inputs_generator.get_calc_type_schema('relax') == {'code_plugin': 'entry.point', 'description': 'test'}


def test_get_relaxation_types(inputs_generator):
    """Test `RelaxInputsGenerator.get_relaxation_types`."""
    assert inputs_generator.get_relaxation_types() == [RelaxType.ATOMS, RelaxType.ATOMS_CELL]
