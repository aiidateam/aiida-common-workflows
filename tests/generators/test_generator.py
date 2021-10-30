# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.generators.generator` module."""
import pytest
from aiida import orm
from aiida.plugins import WorkflowFactory


def test_instan_inputgen(test_inputgen):
    """
    Test the instanciation of a subclass ot `InputGenerator`
    """

    clas = test_inputgen()
    with pytest.raises(RuntimeError):
        clas()

    clas(process_class=WorkflowFactory('common_workflows.relax.siesta'))


def test_serializer(test_inputgen, generate_structure):
    """
    Test the serializer of the arguments of `get_builder`
    """

    clas = test_inputgen(inputs_dict={'structure': orm.StructureData})

    class_ins = clas(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    in_struct = generate_structure(symbols=('Si',))
    buil, args = class_ins.get_builder(structure=in_struct)  # pylint: disable=unused-variable
    # in_struct is an unstored node, therefore it is deepcopied and
    # for this reason the uuid of the initial structure and the one
    # inside `get_builder` are different
    assert args['structure'].uuid != in_struct.uuid

    in_struct = generate_structure(symbols=('Si',)).store()
    buil, args = class_ins.get_builder(structure=in_struct)  # pylint: disable=unused-variable
    # in_struct is now stored, therefore it is maintained
    # within `get_builder`
    assert args['structure'].uuid == in_struct.uuid


def test_serializer_nested(test_inputgen, generate_structure):
    """
    Test the serializer of the arguments of `get_builder` in case of input_namespaces
    """

    clas = test_inputgen(inputs_dict={'space.structure': orm.StructureData}, namespaces=['space'])

    class_ins = clas(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    in_struct = generate_structure(symbols=('Si',))
    buil, args = class_ins.get_builder(space={'structure': in_struct})  # pylint: disable=unused-variable
    # in_struct is an unstored node, therefore it is deepcopied and
    # for this reason the uuid of the initial structure and the one
    # inside `get_builder` are different
    assert args['space']['structure'].uuid != in_struct.uuid

    in_struct = generate_structure(symbols=('Si',)).store()
    buil, args = class_ins.get_builder(space={'structure': in_struct})  # pylint: disable=unused-variable
    # in_struct is now stored, therefore it is maintained
    # within `get_builder`
    assert args['space']['structure'].uuid == in_struct.uuid
