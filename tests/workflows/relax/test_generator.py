# -*- coding: utf-8 -*-
# pylint: disable=abstract-method,arguments-differ,redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.generator` module."""
from typing import Any, Dict, List, Tuple, Union

import pytest

from aiida_common_workflows.protocol import ProtocolRegistry
from aiida_common_workflows.common import RelaxType, SpinType, ElectronicType
from aiida_common_workflows.workflows.relax import CommonRelaxInputGenerator
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
def input_generator(protocol_registry) -> CommonRelaxInputGenerator:
    """Return an instance of a relax input generator implementation."""

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Valid input generator implementation."""

        _engine_types = {'relax': {'code_plugin': 'entry.point', 'description': 'test'}}

        _relax_types = {
            RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
            RelaxType.POSITIONS_CELL: 'Relax both atomic positions and the cell.'
        }

        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}

        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(
            self,
            structure,
            engines: Dict[str, Any],
            *,
            protocol: str = None,
            relax_type: Union[RelaxType, str] = RelaxType.POSITIONS,
            electronic_type: Union[ElectronicType, str] = ElectronicType.METAL,
            spin_type: Union[SpinType, str] = SpinType.NONE,
            magnetization_per_site: Union[List[float], Tuple[float]] = None,
            threshold_forces: float = None,
            threshold_stress: float = None,
            reference_workchain=None,
            **kwargs
        ):
            return super().get_builder(
                structure,
                engines,
                protocol=protocol,
                relax_type=relax_type,
                electronic_type=electronic_type,
                spin_type=spin_type,
                magnetization_per_site=magnetization_per_site,
                threshold_forces=threshold_forces,
                threshold_stress=threshold_stress,
                reference_workchain=reference_workchain,
                **kwargs
            )

    return InputGenerator(process_class=CommonRelaxWorkChain)


def test_validation(protocol_registry):
    """Test the validation of subclasses of `ProtocolRegistry`."""

    # pylint: disable=abstract-class-instantiated,function-redefined,too-many-statements

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no ``get_builder``"""

        _engine_types = None
        _relax_types = None
        _spin_types = None
        _electronic_types = None

    # Abstract `get_builder` method so should raise `TypeError`
    with pytest.raises(TypeError):
        InputGenerator()

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no process class passed."""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator()

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no ``_relax_types``"""

        _engine_types = {'relax': {}}
        _relax_types = None
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no ``_engine_types``"""

        _engine_types = None
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no ``_spin_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = None
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: no ``_electronic_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = None

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_relax_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {'invalid-type': 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_spin_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {'invalid-type': 'description'}
        _electronic_types = {ElectronicType.INSULATOR: '...', ElectronicType.METAL: '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)

    class InputGenerator(protocol_registry, CommonRelaxInputGenerator):
        """Invalid input generator implementation: invalid ``_electronic_types``"""

        _engine_types = {'relax': {}}
        _relax_types = {RelaxType.POSITIONS: 'description'}
        _spin_types = {SpinType.NONE: '...', SpinType.COLLINEAR: '...'}
        _electronic_types = {'invalid_type': '...'}

        def get_builder(self):
            pass

    with pytest.raises(RuntimeError):
        InputGenerator(process_class=CommonRelaxWorkChain)


def test_type_validation(input_generator, generate_structure):
    """Test the validation of the type arguments in ``CommonRelaxInputGenerator.get_builder_from_protocol``."""
    structure = generate_structure()
    engines = {}

    with pytest.raises(TypeError, match=r'.* is neither a string nor a .*'):
        input_generator.get_builder(structure, engines, electronic_type=[])

    with pytest.raises(ValueError, match=r'.* is not a valid ElectronicType'):
        input_generator.get_builder(structure, engines, electronic_type='test')

    with pytest.raises(ValueError, match=r'electronic type `.*` is not supported'):
        input_generator.get_builder(structure, engines, electronic_type='automatic')

    input_generator.get_builder(structure, engines, electronic_type='metal')

    with pytest.raises(TypeError, match=r'.* is neither a string nor a .*'):
        input_generator.get_builder(structure, engines, relax_type=[])

    with pytest.raises(ValueError, match=r'.* is not a valid RelaxType'):
        input_generator.get_builder(structure, engines, relax_type='test')

    with pytest.raises(ValueError, match=r'relax type `.*` is not supported'):
        input_generator.get_builder(structure, engines, relax_type='volume')

    input_generator.get_builder(structure, engines, relax_type='positions')

    with pytest.raises(TypeError, match=r'.* is neither a string nor a .*'):
        input_generator.get_builder(structure, engines, spin_type=[])

    with pytest.raises(ValueError, match=r'.* is not a valid SpinType'):
        input_generator.get_builder(structure, engines, spin_type='test')

    with pytest.raises(ValueError, match=r'spin type `.*` is not supported'):
        input_generator.get_builder(structure, engines, spin_type='spin_orbit')

    input_generator.get_builder(structure, engines, spin_type='collinear')


def test_get_engine_types(input_generator):
    """Test `CommonRelaxInputGenerator.get_engine_types`."""
    assert input_generator.get_engine_types() == ['relax']


def test_get_engine_type_schema(input_generator):
    """Test `CommonRelaxInputGenerator.get_engine_type_schema`."""
    assert input_generator.get_engine_type_schema('relax') == {'code_plugin': 'entry.point', 'description': 'test'}


def test_get_relax_types(input_generator):
    """Test `CommonRelaxInputGenerator.get_relax_types`."""
    assert set(input_generator.get_relax_types()) == {RelaxType.POSITIONS, RelaxType.POSITIONS_CELL}


def test_get_spin_types(input_generator):
    """Test `CommonRelaxInputGenerator.get_spin_types`."""
    assert set(input_generator.get_spin_types()) == {SpinType.NONE, SpinType.COLLINEAR}


def test_get_electronic_types(input_generator):
    """Test `CommonRelaxInputGenerator.get_electronic_types`."""
    assert set(input_generator.get_electronic_types()) == {ElectronicType.INSULATOR, ElectronicType.METAL}
