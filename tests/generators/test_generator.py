# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.generators.generator` module."""
import pytest
from aiida import orm
from aiida.plugins import WorkflowFactory


def test_inputgen_constructor(generate_input_generator_cls):
    """Test the constructor of a subclass of ``InputGenerator``."""

    cls = generate_input_generator_cls()

    with pytest.raises(RuntimeError):
        cls()

    cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))


def test_get_builder_immutable_kwargs(generate_input_generator_cls, generate_structure):
    """
    Test that calling ``get_builder`` does not mutate the ``kwargs`` when they are nodes.
    In this case a deepcopy would mute the node and therefore return a node with different uuid.
    """

    cls = generate_input_generator_cls(inputs_dict={'structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'structure': structure}
    generator.get_builder(**kwargs)
    # The structure is now stored and so should be the same.
    assert kwargs['structure'].uuid == structure.uuid


def test_get_builder_mutable_kwargs(generate_input_generator_cls):
    """
    Test that calling ``get_builder`` does mutate the ``kwargs`` when they are not nodes.
    In this case we want to deepcopy the ``kwargs`` before entering the ``get_builder``.
    In this specific test, we test a particulat input (``mutable``) that is modified inside
    the get_builder of ``generate_input_generator_cls``.
    Here we test that, even if this input is modified inside. This does not affect the
    original ``kwargs`` since it was deepcopied.
    """

    cls = generate_input_generator_cls(inputs_dict={'mutable': dict})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))
    kwargs = {'mutable': {'test': 333}}
    generator.get_builder(**kwargs)
    assert kwargs['mutable'] == {'test': 333}


def test_get_builder_immutable_kwargs_nested(generate_input_generator_cls, generate_structure):
    """
    Test that calling ``get_builder`` does not mutate the ``kwargs`` when they are nodes,
    even if containing nested dictionaries.
    """
    cls = generate_input_generator_cls(inputs_dict={'space.structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'space': {'structure': structure}}
    generator.get_builder(**kwargs)
    assert kwargs['space']['structure'].uuid == structure.uuid
