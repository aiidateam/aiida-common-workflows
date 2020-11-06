# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import click
import pytest

from aiida_common_workflows.cli.launch import cmd_relax, cmd_eos


@pytest.mark.usefixtures('aiida_profile')
def test_relax_wallclock_seconds(run_cli_command, generate_structure, generate_code):
    """Test the `--wallclock-seconds` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-w` should raise as only one value is required
    options = ['-S', str(structure.pk), '-w', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(cmd_relax, options, raises=click.BadParameter)
    assert 'Error: Invalid value for --wallclock-seconds: QuantumEspressoRelaxWorkChain has 1 engine steps, so ' \
           'requires 1 values' in result.output_lines


@pytest.mark.usefixtures('aiida_profile')
def test_relax_number_machines(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-m', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(cmd_relax, options, raises=click.BadParameter)
    assert 'Error: Invalid value for --number-machines: QuantumEspressoRelaxWorkChain has 1 engine steps, so ' \
           'requires 1 values' in result.output_lines


@pytest.mark.usefixtures('aiida_profile')
def test_eos_wallclock_seconds(run_cli_command, generate_structure, generate_code):
    """Test the `--wallclock-seconds` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-w` should raise as only one value is required
    options = ['-S', str(structure.pk), '-w', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(cmd_eos, options, raises=click.BadParameter)
    assert 'Error: Invalid value for --wallclock-seconds: QuantumEspressoRelaxWorkChain has 1 engine steps, so ' \
           'requires 1 values' in result.output_lines


@pytest.mark.usefixtures('aiida_profile')
def test_eos_number_machines(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-m', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(cmd_eos, options, raises=click.BadParameter)
    assert 'Error: Invalid value for --number-machines: QuantumEspressoRelaxWorkChain has 1 engine steps, so ' \
           'requires 1 values' in result.output_lines


@pytest.mark.usefixtures('aiida_profile')
def test_eos_relax_types(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-r', 'cell', 'quantum_espresso']
    result = run_cli_command(cmd_eos, options, raises=click.BadParameter)
    assert 'Error: Invalid value for "-r" / "--relaxation-type": invalid choice: cell. ' \
           '(choose from none, atoms, shape, atoms_shape)' in result.output_lines
