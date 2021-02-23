# -*- coding: utf-8 -*-
# pylint: disable=abstract-method,arguments-differ,redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.generator` module."""
import pytest

from aiida_common_workflows.protocol import ProtocolRegistry
from aiida_common_workflows.common import RelaxType, SpinType, ElectronicType
from aiida_common_workflows.workflows.relax import RelaxInputGenerator
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture
def protocol_registry() -> ProtocolRegistry:
    """Return an instance of a protocol registry implementation."""

    class SubProtocolRegistry(ProtocolRegistry):
        """Valid protocol registry implementation."""

        _protocols = {'efficiency': {'description': 'description'}, 'precision': {'description': 'description'}}
        _default_protocol = 'efficiency'

    return SubProtocolRegistry


@pytest.fixture
def inputs_generator(protocol_registry) -> RelaxInputGenerator:
    """Return an instance of a relax input generator implementation."""

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Valid input generator implementation."""

        _engine_types = {'relax': {'code_plugin': 'entry.point', 'description': 'test'}}

        _relax_types = {
            RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
            RelaxType.POSITIONS_CELL: 'Relax both atomic positions and the cell.'
        }

        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}

        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    return InputGenerator(process_class=CommonRelaxWorkChain)


def test_validation(protocol_registry):
    """Test the validation of subclasses of `ProtocolRegistry`."""

    # pylint: disable=abstract-class-instantiated,function-redefined,too-many-statements

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no ``get_builder``"""

        _engine_types = None
        _relax_types = None
        _spin_types = None
        _electronic_types = None

    # Abstract `get_builder` method so should raise `TypeError`
    with pytest.raises(TypeError):
        InputGenerator()

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no process class passed."""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator()

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no ``_relax_types``"""

        _engine_types = {'relax': {}}
        _relax_types = None
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no ``_engine_types``"""

        _engine_types = None
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no ``_spin_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = None
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: no ``_electronic_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = None

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_relax_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {'invalid-type': 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_spin_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {'invalid-type': 'description'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, RelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_electronic_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {'invalid_type': '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)


def test_get_engine_types(inputs_generator):
    """Test `RelaxInputGenerator.get_engine_types`."""
    assert inputs_generator.get_engine_types() == ['relax']


def test_get_engine_type_schema(inputs_generator):
    """Test `RelaxInputGenerator.get_engine_type_schema`."""
    assert inputs_generator.get_engine_type_schema('relax') == {'code_plugin': 'entry.point', 'description': 'test'}


def test_get_relax_types(inputs_generator):
    """Test `RelaxInputGenerator.get_relax_types`."""
    assert set(inputs_generator.get_relax_types()) == {RelaxType.POSITIONS, RelaxType.POSITIONS_CELL}


def test_get_spin_types(inputs_generator):
    """Test `RelaxInputGenerator.get_spin_types`."""
    assert set(inputs_generator.get_spin_types()) == {SpinType.NONE, SpinType.COLLINEAR}


def test_get_electronic_types(inputs_generator):
    """Test `RelaxInputGenerator.get_electronic_types`."""
    assert set(inputs_generator.get_electronic_types()) == {ElectronicType.INSULATOR, ElectronicType.METAL}
