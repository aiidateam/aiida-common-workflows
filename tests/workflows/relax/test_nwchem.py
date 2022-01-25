# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.nwchem` module."""
# pylint: disable=redefined-outer-name
from aiida import engine, plugins
import pytest

WORKCHAIN = plugins.WorkflowFactory('common_workflows.relax.nwchem')
GENERATOR = WORKCHAIN.get_input_generator()


@pytest.fixture
def default_builder_inputs(generate_code, generate_structure):
    """Return a dictionary with minimum required inputs for the ``get_builder`` method of the inputs generator."""
    return {
        'structure': generate_structure(symbols=('Si',)),
        'engines': {
            'relax': {
                'code': generate_code('nwchem.nwchem').store().uuid,
                'options': {
                    'resources': {
                        'num_machines': 1,
                        'tot_num_mpiprocs': 1
                    }
                }
            }
        },
    }


def test_get_builder(default_builder_inputs):
    """Test the ``get_builder`` with default arguments."""
    builder = GENERATOR.get_builder(**default_builder_inputs)
    assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.skip('Running this test will fail with an `UnroutableError` in `kiwipy`.')
def test_submit(default_builder_inputs):
    """Test submitting the builder returned by ``get_builder`` called with default arguments.

    This will actually create the ``WorkChain`` instance, so if it doesn't raise, that means the input spec was valid.
    """
    builder = GENERATOR.get_builder(**default_builder_inputs)
    engine.submit(builder)


def test_supported_electronic_types(default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``electronic_types``."""
    inputs = default_builder_inputs

    for electronic_type in GENERATOR.spec().inputs['electronic_type'].choices:
        inputs['electronic_type'] = electronic_type
        builder = GENERATOR.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


def test_supported_relax_types(default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``relax_types``."""
    inputs = default_builder_inputs

    for relax_type in GENERATOR.spec().inputs['relax_type'].choices:
        inputs['relax_type'] = relax_type
        builder = GENERATOR.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


def test_supported_spin_types(default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``spin_types``."""
    inputs = default_builder_inputs

    for spin_type in GENERATOR.spec().inputs['spin_type'].choices:
        inputs['spin_type'] = spin_type
        builder = GENERATOR.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)
