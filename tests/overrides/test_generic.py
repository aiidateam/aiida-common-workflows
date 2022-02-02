# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.overrides.generic` module."""
from aiida import orm
from importlib_metadata import entry_points
import pytest


def test_updated_dict(get_empty_builder):
    """
    Test the override function `generic.update_dict`.

    Its signature is generic.update_dict(builder, port, dictionary, sub_path)
    """

    found = entry_points().select(group='acwf.overrides', name='generic.update_dict')

    assert len(found) == 1

    override_func = found['generic.update_dict'].load()

    builder = get_empty_builder('common_workflows.relax.siesta')
    builder.parameters = orm.Dict(dict={'test': 1})
    save_uuid = builder.parameters.uuid

    #Fail because port is not string
    with pytest.raises(ValueError):
        override_func(builder, {'not_a', 'string'}, {'new_dict': 33})

    #Fail because the specified port is invalid
    with pytest.raises(ValueError):
        override_func(builder, 'not_valid_port', {'new_dict': 33})

    #Fail because the `dictionary` is not a `dict`
    with pytest.raises(ValueError):
        override_func(builder, 'parameters', 'not_a_dict')

    #Ok, no stored node
    override_func(builder, 'parameters', {'new_dict': 33})
    assert builder.parameters.get_dict() == {'new_dict': 33, 'test': 1}
    assert builder.parameters.uuid == save_uuid

    #Ok, stored node
    builder.parameters = orm.Dict(dict={'test': 1}).store()
    save_uuid = builder.parameters.uuid
    override_func(builder, 'parameters', {'new_dict': 33})
    assert builder.parameters.get_dict() == {'new_dict': 33, 'test': 1}
    assert not builder.parameters.uuid == save_uuid

    builder = get_empty_builder('common_workflows.relax.siesta')
    builder.parameters = orm.Dict(dict={'test': {'nested': 1}})

    #Fail because the key in sub_path is not present
    with pytest.raises(ValueError):
        override_func(builder, 'parameters', {'new_dict': 33}, sub_path='w')

    override_func(builder, 'parameters', {'new_dict': 33}, sub_path='test')
    assert builder.parameters.get_dict() == {'test': {'nested': 1, 'new_dict': 33}}

    override_func(builder, 'parameters', {'new_dict': 44}, sub_path='test')
    assert builder.parameters.get_dict() == {'test': {'nested': 1, 'new_dict': 44}}

    #NOTE: for now override_func(builder, "parameters", {"new_dict":33}, sub_path=["test","nested"])
    #fails. Is it correct or should I replace `{"nested":1}` with `{"nested":{"new_dict":33}}?

    builder = get_empty_builder('common_workflows.relax.siesta')
    builder.parameters = orm.Dict(dict={'test': {'double': {'nested': 1}}})
    override_func(builder, 'parameters', {'new_dict': 33}, sub_path=['test', 'double'])
    assert builder.parameters.get_dict() == {'test': {'double': {'nested': 1, 'new_dict': 33}}}


def test_add_or_replace_node(get_empty_builder):
    """
    Test the override function `generic.add_or_replace_node`.

    Its signature is generic.add_or_replace_node(builder, port, new_node)
    """
    found = entry_points().select(group='acwf.overrides', name='generic.add_or_replace_node')

    assert len(found) == 1

    override_func = found['generic.add_or_replace_node'].load()

    builder = get_empty_builder('common_workflows.relax.siesta')
    builder.parameters = orm.Dict(dict={'test': 1})

    #Fail for invalid uuid
    with pytest.raises(ValueError):
        override_func(builder, 'parameters', 'ww')

    new_node = orm.Dict(dict={'test_b': 2})
    new_node.store()
    override_func(builder, 'parameters', new_node.uuid)
    assert builder.parameters.get_dict() == {'test_b': 2}


def test_remove_node(get_empty_builder):
    """
    Test the override function `generic.remove_node`.

    Its signature is generic.remove_node(builder, port)
    """
    found = entry_points().select(group='acwf.overrides', name='generic.remove_node')

    assert len(found) == 1

    override_func = found['generic.remove_node'].load()

    builder = get_empty_builder('common_workflows.relax.siesta')
    builder.parameters = orm.Dict(dict={'test': 1})

    #Fail for invalid uuid
    with pytest.raises(ValueError):
        override_func(builder, 'ww')

    override_func(builder, 'parameters')
    assert 'parameters' not in builder
