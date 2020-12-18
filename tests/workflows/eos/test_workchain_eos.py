# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.eos` module."""
import pytest

from aiida import orm
from aiida.engine import WorkChain
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows import eos
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain
from aiida_common_workflows.workflows.relax.generator import RelaxType


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
        assert eos.validate_sub_process_class(value, ctx) == message


@pytest.mark.usefixtures('with_database')
def test_validate_sub_process_class_plugins(ctx, common_relax_workchain):
    """Test the `validate_sub_process_class` validator."""
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    assert eos.validate_sub_process_class(get_entry_point_name_from_class(common_relax_workchain).name, ctx) is None


@pytest.mark.usefixtures('with_database')
def test_validate_inputs(ctx):
    """Test the `validate_inputs` validator."""
    value = {}
    assert eos.validate_inputs(
        value, ctx
    ) == 'neither `scale_factors` nor the pair of `scale_count` and `scale_increment` were defined.'
    value = {'scale_count': 2}
    assert eos.validate_inputs(
        value, ctx
    ) == 'neither `scale_factors` nor the pair of `scale_count` and `scale_increment` were defined.'
    value = {'scale_increment': 2}
    assert eos.validate_inputs(
        value, ctx
    ) == 'neither `scale_factors` nor the pair of `scale_count` and `scale_increment` were defined.'
    value = {'scale_count': 2, 'scale_increment': 0.2}
    assert eos.validate_inputs(value, ctx) is None
    value = {'scale_factors': []}
    assert eos.validate_inputs(value, ctx) is None


@pytest.mark.usefixtures('with_database')
def test_validate_scale_factors(ctx):
    """Test the `validate_scale_factors` validator."""
    assert eos.validate_scale_factors(None, ctx) is None
    assert eos.validate_scale_factors(orm.List(list=[0.98, 1, 1.02]), ctx) is None

    assert eos.validate_scale_factors(orm.List(list=[0, 1]), ctx) == 'need at least 3 scaling factors.'


@pytest.mark.usefixtures('with_database')
def test_validate_scale_count(ctx):
    """Test the `validate_scale_count` validator."""
    assert eos.validate_scale_count(None, ctx) is None
    assert eos.validate_scale_count(orm.Int(3), ctx) is None

    assert eos.validate_scale_count(orm.Int(2), ctx) == 'need at least 3 scaling factors.'


@pytest.mark.usefixtures('with_database')
def test_validate_scale_increment(ctx):
    """Test the `validate_scale_increment` validator."""
    assert eos.validate_scale_increment(None, ctx) is None
    assert eos.validate_scale_increment(orm.Float(0.5), ctx) is None

    assert eos.validate_scale_increment(orm.Float(0), ctx) == 'scale increment needs to be between 0 and 1.'
    assert eos.validate_scale_increment(orm.Float(1), ctx) == 'scale increment needs to be between 0 and 1.'
    assert eos.validate_scale_increment(orm.Float(-0.0001), ctx) == 'scale increment needs to be between 0 and 1.'
    assert eos.validate_scale_increment(orm.Float(1.00001), ctx) == 'scale increment needs to be between 0 and 1.'


@pytest.mark.usefixtures('with_database')
def test_validate_relax_type(ctx):
    """Test the `validate_relax_type` validator."""
    assert eos.validate_relax_type(RelaxType.NONE, ctx) is None
    assert eos.validate_relax_type(
        RelaxType.CELL, ctx
    ) == '`generator_inputs.relax_type`. Equation of state and relaxation with variable volume not compatible.'
