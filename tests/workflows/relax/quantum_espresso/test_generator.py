# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso.generator` module."""
import pytest

from aiida.plugins import WorkflowFactory
from aiida_common_workflows.workflows.relax.quantum_espresso import QuantumEspressoRelaxInputsGenerator

PwRelaxWorkChain = WorkflowFactory('quantumespresso.pw.relax')


def test_construction_fail():
    """Test that the generator constructor raises if no `process_class` is defined."""
    with pytest.raises(RuntimeError, match=r'.*required keyword argument `process_class` was not defined.'):
        QuantumEspressoRelaxInputsGenerator()


def test_construction():
    """Test that the generator can be successfully constructed, meaning class attributes have been correctly defined."""
    QuantumEspressoRelaxInputsGenerator(process_class=PwRelaxWorkChain)
