# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.generators.generator` module."""
import pytest
from aiida import orm
from aiida.plugins import WorkflowFactory


def test_inputgen_constructor(generate_input_generator_class):
    """Test the constructor of a subclass of ``InputGenerator``."""
    
    cls = generate_input_generator_class()
    
    with pytest.raises(RuntimeError):
        cls()

    cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))


def test_get_builder_immutable_kwargs(test_inputgen, generate_structure):
    """Test that calling ``get_builder`` does not mutate the ``kwargs``."""

    cls = generate_input_generator_cls(inputs_dict={'structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'structure': structure}
    generator.get_builder(**kwargs)
    # structure is an unstored node, therefore it is deepcopied and so the UUID should change.
    assert kwargs['structure'].uuid != structure.uuid

    structure = generate_structure(symbols=('Si',)).store()
    kwargs = {'structure': structure}
    generator.get_builder(**kwargs)
    # The structure is now stored and so should be the same.
    assert kwargs['structure'].uuid == structure.uuid


def test_get_builder_immutable_kwargs_nested(test_inputgen, generate_structure):
    """Test that calling ``get_builder`` does not mutate the ``kwargs`` even if containing nested dictionaries."""
    cls = generate_input_generator_cls(inputs_dict={'space.structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'space': {'structure': structure}}
    generator.get_builder(**kwargs)
    # structure is an unstored node, therefore it is deepcopied and so the UUID should change.
    assert kwargs['space']['structure'].uuid != structure.uuid

    structure = generate_structure(symbols=('Si',)).store()
    kwargs = {'space': {'structure': structure}}
    generator.get_builder(**kwargs)
    # The structure is now stored and so should be the same.
    assert kwargs['space']['structure'].uuid == structure.uuid
