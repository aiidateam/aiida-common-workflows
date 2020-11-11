# -*- coding: utf-8 -*-
# pylint: disable=abstract-method,arguments-differ,redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.generator` module."""
import pytest

from aiida_common_workflows.protocol import ProtocolRegistry
from aiida_common_workflows.workflows.relax import RelaxInputsGenerator, RelaxType, SpinType
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
def inputs_generator(protocol_registry) -> RelaxInputsGenerator:
    """Return an instance of a relax inputs generator implementation."""

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Valid inputs generator implementation."""

        _calc_types = {'relax': {'code_plugin': 'entry.point', 'description': 'test'}}

        _relax_types = {
            RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
            RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
        }

        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}

        def get_builder(self):
            pass

    return InputsGenerator(process_class=CommonRelaxWorkChain)


def test_validation(protocol_registry):
    """Test the validation of subclasses of `ProtocolRegistry`."""

    # pylint: disable=abstract-class-instantiated,function-redefined

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation: no ``get_builder``"""

        _calc_types = None
        _relax_types = None
        _spin_types = None

    # Abstract `get_builder` method so should raise `TypeError`
    with pytest.raises(TypeError):
        InputsGenerator()

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation: no process class passed."""

        _calc_types = {'relax': {}}
        _relax_types = {RelaxType.ATOMS: 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator()

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation: no ``_relax_types``"""

        _calc_types = {'relax': {}}
        _relax_types = None
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator(process_class=CommonRelaxWorkChain)

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation. No calc_types"""

        _calc_types = None
        _relax_types = {RelaxType.ATOMS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator(process_class=CommonRelaxWorkChain)

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation. No spin_types"""

        _calc_types = {'relax': {}}
        _relax_types = {RelaxType.ATOMS: 'description'}
        _spin_types = None

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator(process_class=CommonRelaxWorkChain)

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation. Invalid _relax_types"""

        _calc_types = {'relax': {}}
        _relax_types = {'invalid-type': 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator(process_class=CommonRelaxWorkChain)

    class InputsGenerator(protocol_registry, RelaxInputsGenerator):
        """Invalid inputs generator implementation. Invalid _relax_types"""

        _calc_types = {'relax': {}}
        _relax_types = {RelaxType.ATOMS: 'description'}
        _spin_types = {'invalid-type': 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputsGenerator(process_class=CommonRelaxWorkChain)


def test_get_calc_types(inputs_generator):
    """Test `RelaxInputsGenerator.get_calc_types`."""
    assert inputs_generator.get_calc_types() == ['relax']


def test_get_calc_type_schema(inputs_generator):
    """Test `RelaxInputsGenerator.get_calc_type_schema`."""
    assert inputs_generator.get_calc_type_schema('relax') == {'code_plugin': 'entry.point', 'description': 'test'}


def test_get_relaxation_types(inputs_generator):
    """Test `RelaxInputsGenerator.get_relaxation_types`."""
    assert set(inputs_generator.get_relaxation_types()) == {RelaxType.ATOMS, RelaxType.ATOMS_CELL}


def test_get_spin_types(inputs_generator):
    """Test `RelaxInputsGenerator.get_spin_types`."""
    assert set(inputs_generator.get_spin_types()) == set([SpinType.NONE, SpinType.COLLINEAR])
