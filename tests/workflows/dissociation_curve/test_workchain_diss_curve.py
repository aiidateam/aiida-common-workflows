# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.dissociation` module."""
import pytest

from aiida import orm
from aiida.engine import WorkChain
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows import dissociation
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture
def ctx():
    """Return the context for a port validator."""
    return None


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('relax'))
def common_relax_workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return WorkflowFactory(request.param)


@pytest.mark.usefixtures('with_database')
def test_validate_sub_process_class(ctx):
    """Test the `validate_sub_process_class` validator."""
    for value in [None, WorkChain]:
        message = f'`{value}` is not a valid or registered workflow entry point.'
        assert dissociation.validate_sub_process_class(value, ctx) == message


@pytest.mark.usefixtures('with_database')
def test_validate_sub_process_class_plugins(ctx, common_relax_workchain):
    """Test the `validate_sub_process_class` validator."""
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    assert dissociation.validate_sub_process_class(
        get_entry_point_name_from_class(common_relax_workchain).name, ctx
    ) is None


@pytest.mark.usefixtures('with_database')
def test_validate_inputs(ctx):
    """Test the `validate_inputs` validator."""
    value = {}
    assert dissociation.validate_inputs(
        value, ctx
    ) == 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
    value = {'distances_count': 3, 'distance_min': 0.5}
    assert dissociation.validate_inputs(
        value, ctx
    ) == 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
    value = {'distances_count': 3, 'distance_max': 1.5}
    assert dissociation.validate_inputs(
        value, ctx
    ) == 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
    value = {'distance_max': 2, 'distance_min': 0.5}
    assert dissociation.validate_inputs(
        value, ctx
    ) == 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
    value = {'distance_max': 2, 'distance_min': 0.5, 'distances_count': 3}
    assert dissociation.validate_inputs(value, ctx) is None
    value = {'distances': []}
    assert dissociation.validate_inputs(value, ctx) is None
    value = {'distances': [], 'distance_min': 0.5}
    assert dissociation.validate_inputs(value, ctx) is None
    value = {'distance_max': 2, 'distance_min': 5, 'distances_count': 3}
    assert dissociation.validate_inputs(value, ctx) == '`distance_min` must be smaller than `distance_max`'


@pytest.mark.usefixtures('with_database')
def test_validate_molecule(ctx, generate_structure):
    """Test the `validate_molecule` validator."""
    molecule = generate_structure()
    assert dissociation.validate_molecule(molecule, ctx) == '`molecule`. only diatomic molecules are supported.'
    molecule.append_atom(position=(0.000, 0.000, 0.000), symbols=['Si'])
    molecule.append_atom(position=(0.250, 0.250, 0.250), symbols=['Si'])
    assert dissociation.validate_molecule(molecule, ctx) is None


@pytest.mark.usefixtures('with_database')
def test_validate_distances(ctx):
    """Test the `validate_scale_factors` validator."""
    assert dissociation.validate_distances(None, ctx) is None
    assert dissociation.validate_distances(orm.List(list=[0.98, 1, 1.02]), ctx) is None

    assert dissociation.validate_distances(orm.List(list=[0]), ctx) == 'need at least 2 distances.'
    assert dissociation.validate_distances(orm.List(list=[-1, -2, -2]), ctx) == 'distances must be positive.'


@pytest.mark.usefixtures('with_database')
def test_validate_distances_count(ctx):
    """Test the `validate_scale_count` validator."""
    assert dissociation.validate_distances_count(None, ctx) is None
    assert dissociation.validate_distances_count(orm.Int(3), ctx) is None

    assert dissociation.validate_distances_count(orm.Int(1), ctx) == 'need at least 2 distances.'


@pytest.mark.usefixtures('with_database')
def test_validate_distance_max(ctx):
    """Test the `validate_distance_max` validator."""
    assert dissociation.validate_distance_max(None, ctx) is None
    assert dissociation.validate_distance_max(orm.Float(0.5), ctx) is None

    assert dissociation.validate_distance_max(orm.Float(-0.5), ctx) == '`distance_max` must be bigger than zero.'


@pytest.mark.usefixtures('with_database')
def test_validate_distance_min(ctx):
    """Test the `validate_scale_increment` validator."""
    assert dissociation.validate_distance_min(None, ctx) is None
    assert dissociation.validate_distance_min(orm.Float(0.5), ctx) is None

    assert dissociation.validate_distance_min(orm.Float(-0.5), ctx) == '`distance_min` must be bigger than zero.'
