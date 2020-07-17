# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso.workchain` module."""
from aiida_common_workflows.workflows.relax.quantum_espresso import QuantumEspressoRelaxWorkChain
from aiida_common_workflows.workflows.relax.quantum_espresso import QuantumEspressoRelaxInputsGenerator


def test_get_inputs_generator():
    """Test the `get_inputs_generator` class property."""
    assert isinstance(QuantumEspressoRelaxWorkChain.get_inputs_generator(), QuantumEspressoRelaxInputsGenerator)
