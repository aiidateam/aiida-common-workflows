# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.frozen_phonons` module."""
from aiida import orm
from aiida.engine import WorkChain
from aiida.plugins import WorkflowFactory
import pytest

from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.phonons import frozen_phonons
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture
def ctx():
    """Return the context for a port validator."""
    return None


@pytest.fixture
def generate_phonopy_calcjob_node():
    """Generate an instance of `CalcJobNode`."""

    def _generate_phonopy_calcjob_node(exit_status=0):
        from aiida import orm
        from aiida.common import LinkType
        from plumpy import ProcessState

        node = orm.CalcJobNode().store()
        node.set_process_state(ProcessState.FINISHED)
        node.set_exit_status(exit_status)

        parameters = orm.Dict({'some': 'output'}).store()
        parameters.base.links.add_incoming(node, link_type=LinkType.CREATE, link_label='output_parameters')

        return node

    return _generate_phonopy_calcjob_node


@pytest.fixture
def generate_workchain_node():
    """Generate an instance of `WorkflowNode`."""

    def _generate_workchain_node(exit_status=0):
        from aiida import orm
        from aiida.common import LinkType
        import numpy as np
        from plumpy import ProcessState

        node = orm.WorkflowNode().store()
        node.set_process_state(ProcessState.FINISHED)
        node.set_exit_status(exit_status)

        forces = orm.ArraData()
        forces.set_array('forces', np.zeros((2, 3)))
        forces.store()
        forces.base.links.add_incoming(node, link_type=LinkType.RETURN, link_label='forces')

        return node

    return _generate_workchain_node


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('relax'))
def common_relax_workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return WorkflowFactory(request.param)


@pytest.fixture
@pytest.mark.usefixtures('aiida_profile')
def generate_frozen_phonons_inputs(generate_structure, generate_code):
    """Return a dictionary of defaults inputs for the ``FrozenPhononsWorkChain``."""

    def _generate_frozen_phonons_inputs():
        return {
            'structure': generate_structure(symbols=('Si',)),
            'supercell_matrix': orm.List([2, 2, 2]),
            'displacement_generator': orm.Dict({'distance': 0.01}),
            'symmetry': {
                'symprec': orm.Float(1e-5),
                'distinguish_kinds': orm.Bool(True),
                'is_symmetry': orm.Bool(True)
            },
            'phonopy': {
                'code': generate_code('phonopy.phonopy').store(),
                'parameters': orm.Dict({'band': 'auto'}),
            },
            'sub_process_class': 'common_workflows.relax.quantum_espresso',
            'generator_inputs': {
                'protocol': 'fast',
                'engines': {
                    'relax': {
                        'code': generate_code('quantumespresso.pw').store(),
                        'options': {
                            'resources': {
                                'num_machines': 1
                            }
                        }
                    }
                },
                'electronic_type': 'metal',
            }
        }

    return _generate_frozen_phonons_inputs


def test_validate_sub_process_class(ctx):
    """Test the `validate_sub_process_class` validator."""
    for value in [None, WorkChain]:
        message = f'`{value}` is not a valid or registered workflow entry point.'
        assert frozen_phonons.validate_sub_process_class(value, ctx) == message


def test_validate_sub_process_class_plugins(ctx, common_relax_workchain):
    """Test the `validate_sub_process_class` validator."""
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    assert frozen_phonons.validate_sub_process_class(
        get_entry_point_name_from_class(common_relax_workchain).name, ctx
    ) is None


@pytest.mark.usefixtures('sssp')
def test_validate_inputs_generator_inputs(ctx, generate_frozen_phonons_inputs):
    """Test the ``validate_inputs`` validator for invalid generator inputs."""
    value = generate_frozen_phonons_inputs()
    assert frozen_phonons.validate_inputs(value, ctx) is None

    value['generator_inputs']['electronic_type'] = 'invalid_value'
    assert "invalid_value' is not a valid ElectronicType" in frozen_phonons.validate_inputs(value, ctx)


def test_validate_matrix(ctx):
    """Test the `validate_matrix` validator."""
    assert frozen_phonons.validate_matrix(orm.List([1, 1, 1]), ctx) is None
    assert frozen_phonons.validate_matrix(orm.List([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), ctx) is None
    assert frozen_phonons.validate_matrix(orm.List([1, 1]), ctx) == 'need exactly 3 diagonal elements or 3x3 arrays.'
    # element = 'a'
    # message = f'type `{type(element)}` of {element} is not an accepted type in matrix; only `int` and `float` are valid.'
    # assert frozen_phonons.validate_matrix(orm.List([element,element,element]), ctx) == message
    assert frozen_phonons.validate_matrix(orm.List([[1], [1], [1]]), ctx) == 'matrix need to have 3x1 or 3x3 shape.'


@pytest.mark.usefixtures('sssp')
def test_run_init(generate_workchain, generate_frozen_phonons_inputs):
    """Test the ``FrozenPhononsWorkChain.run_init`` method."""
    inputs = generate_frozen_phonons_inputs()
    process = generate_workchain('common_workflows.phonons.frozen_phonons', inputs)

    process.run_init()
    assert 'preprocess_data' in process.ctx
    assert f'{frozen_phonons.FrozenPhononsWorkChain._RUN_PREFIX}_0' in process.ctx
    assert 'structures' in process.ctx
    assert len(process.ctx['structures']) == 1


@pytest.mark.usefixtures('sssp')
def test_inspect_init(generate_workchain, generate_frozen_phonons_inputs, generate_workchain_node):
    """Test the ``FrozenPhononsWorkChain.inspect_init`` method."""
    inputs = generate_frozen_phonons_inputs()
    process = generate_workchain('common_workflows.phonons.frozen_phonons', inputs)

    label = f'{frozen_phonons.FrozenPhononsWorkChain._RUN_PREFIX}_0'
    process.ctx[label] = generate_workchain_node()

    results = process.inspect_init()
    assert results is None


@pytest.mark.usefixtures('sssp')
def test_run_supercells(generate_workchain, generate_frozen_phonons_inputs):
    """Test the ``FrozenPhononsWorkChain.run_supercells`` method."""
    inputs = generate_frozen_phonons_inputs()
    process = generate_workchain('common_workflows.phonons.frozen_phonons', inputs)
    prefix = f'{frozen_phonons.FrozenPhononsWorkChain._RUN_PREFIX}_'

    process.run_init()
    process.run_supercells()
    assert f'{prefix}_1' in process.ctx

    assert len(process.ctx['supercells']) == 2


@pytest.mark.usefixtures('sssp')
def test_inspect_supercells(generate_workchain, generate_frozen_phonons_inputs, generate_workchain_node):
    """Test the ``FrozenPhononsWorkChain.inspect_supercells`` method."""
    inputs = generate_frozen_phonons_inputs()
    process = generate_workchain('common_workflows.phonons.frozen_phonons', inputs)
    prefix = f'{frozen_phonons.FrozenPhononsWorkChain._RUN_PREFIX}_'

    process.run_init()
    process.run_supercells()

    process.ctx[f'{prefix}_0'] = generate_workchain_node()
    process.ctx[f'{prefix}_1'] = generate_workchain_node()

    results = process.inspect_supercells()
    assert results is None


@pytest.mark.usefixtures('sssp')
def test_should_run_phonopy(generate_workchain, generate_frozen_phonons_inputs):
    """Test the ``FrozenPhononsWorkChain.should_run_phonopy`` method."""
    inputs = generate_frozen_phonons_inputs()
    process = generate_workchain('common_workflows.phonons.frozen_phonons', inputs)

    assert process.should_run_phonopy()
