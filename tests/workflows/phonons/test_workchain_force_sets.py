# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Tests for the :mod:`aiida_common_workflows.workflows.common_force_sets` module."""
import pytest

from aiida.engine import WorkChain
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.plugins import get_workflow_entry_point_names
from aiida_common_workflows.workflows.phonons import common_force_sets
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@pytest.fixture
def ctx():
    """Return the context for a port validator."""
    return None


@pytest.fixture(scope='function', params=get_workflow_entry_point_names('relax'))
def common_relax_workchain(request) -> CommonRelaxWorkChain:
    """Fixture that parametrizes over all the registered implementations of the ``CommonRelaxWorkChain``."""
    return WorkflowFactory(request.param)


@pytest.fixture
def generate_workchain():
    """Generate an instance of a `WorkChain`."""

    def _generate_workchain(entry_point, inputs):
        """Generate an instance of a `WorkChain` with the given entry point and inputs.

        :param entry_point: entry point name of the work chain subclass.
        :param inputs: inputs to be passed to process construction.
        :return: a `WorkChain` instance.
        """
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import WorkflowFactory

        process_class = WorkflowFactory(entry_point)
        runner = get_manager().get_runner()
        process = instantiate_process(runner, process_class, **inputs)

        return process

    return _generate_workchain

@pytest.fixture
def generate_workchain_force_sets(generate_workchain, generate_structure, generate_code):
    """Generate an instance of a `ForceSetsWorkChain`."""

    def _generate_workchain_force_sets(append_inputs=None, return_inputs=False):
        from aiida.orm import List
        entry_point = 'common_workflows.phonons.force_sets'

        inputs = {
            'structure': generate_structure(symbols=('Si',)), 
            'supercell_matrix': List(list=[1,1,1]),
            'sub_process_class': 'common_workflows.relax.quantum_espresso',
            'generator_inputs': {
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
                'electronic_type': 'insulator',
                'protocol': 'moderate',
            },
        }

        if return_inputs:
            return inputs
        
        if append_inputs is not None:
            inputs.update(append_inputs)

        process = generate_workchain(entry_point, inputs)

        return process

    return _generate_workchain_force_sets


def test_validate_sub_process_class(ctx):
    """Test the `validate_sub_process_class` validator."""
    for value in [None, WorkChain]:
        message = f'`{value}` is not a valid or registered workflow entry point.'
        assert common_force_sets.validate_sub_process_class(value, ctx) == message


def test_validate_sub_process_class_plugins(ctx, common_relax_workchain):
    """Test the `validate_sub_process_class` validator."""
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    assert common_force_sets.validate_sub_process_class(get_entry_point_name_from_class(common_relax_workchain).name, ctx) is None


@pytest.mark.usefixtures('sssp')
def test_run_forces(generate_workchain_force_sets):
    """Test `CommonForceSetsWorkChain.run_forces`."""
    process = generate_workchain_force_sets()
    process.setup()
    process.run_forces()

    for key in ['cells', 'primitive_matrix', 'displacement_dataset']:
        assert key in process.outputs

    for key in ['primitive', 'supercell', 'supercell_1']:
        assert key in process.outputs['cells']

    # Double check for the `setup` method (already tested in `aiida-phonopy`).
    assert 'primitive' not in process.ctx.supercells
    assert 'supercell' not in process.ctx.supercells
    assert 'supercell_1' in process.ctx.supercells    

    # Check for 
    assert 'force_calc_1' in process.ctx

@pytest.mark.usefixtures('sssp')
def test_outline(generate_workchain_force_sets):
    """Test `CommonForceSetsWorkChain` outline."""
    from plumpy.process_states import ProcessState
    from aiida.common import LinkType
    from aiida.orm import WorkflowNode, ArrayData, Float
    import numpy as np
    
    process = generate_workchain_force_sets()
    
    node = WorkflowNode().store()
    node.label = 'force_calc_1'
    forces = ArrayData()
    forces.set_array('forces', np.array([[0.,0.,0.],[0.,0.,0.]]))
    forces.store()
    forces.add_incoming(node, link_type=LinkType.RETURN, link_label='forces')
    energy = Float(0.).store()
    energy.add_incoming(node, link_type=LinkType.RETURN, link_label='total_energy')
    
    node.set_process_state(ProcessState.FINISHED)
    node.set_exit_status(0)
    
    process.ctx.force_calc_1 = node
    
    process.inspect_forces()

    assert 'force_calc_1' in process.outputs['supercells_forces']
    assert 'forces' in process.ctx
    assert 'forces_1' in process.ctx.forces
    
    process.run_results()
    
    assert 'force_sets' in process.outputs
    
    
@pytest.mark.usefixtures('sssp')
def test_run_outline_with_subtracting_residual_forces(generate_workchain_force_sets):
    """Test `CommonForceSetsWorkChain.run_forces`."""
    from aiida.orm import Bool
    process = generate_workchain_force_sets(append_inputs={'subtract_residual_forces':Bool(True)})
    process.setup()
    process.run_forces()

    for key in ['cells', 'primitive_matrix', 'displacement_dataset']:
        assert key in process.outputs

    for key in ['primitive', 'supercell', 'supercell_1']:
        assert key in process.outputs['cells']

    # Double check for the `setup` method (already tested in `aiida-phonopy`).
    assert 'primitive' not in process.ctx.supercells
    assert 'supercell' in process.ctx.supercells
    assert 'supercell_1' in process.ctx.supercells    

    # Check for 
    assert 'force_calc_0' in process.ctx
    assert 'force_calc_1' in process.ctx