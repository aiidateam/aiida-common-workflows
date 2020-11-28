# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import click
import pytest

from aiida_common_workflows.cli import utils
from aiida_common_workflows.cli.launch import cmd_relax, cmd_eos, cmd_plot_eos


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


@pytest.mark.usefixtures('clear_database_before_test')
def test_relax_codes(run_cli_command, generate_structure, generate_code, monkeypatch):
    """Test the `--codes` option."""

    def launch_process(_, __):
        pass

    monkeypatch.setattr(utils, 'launch_process', launch_process)
    structure = generate_structure().store()

    # No codes available
    options = ['-S', str(structure.pk), 'fleur']
    result = run_cli_command(cmd_relax, options, raises=click.UsageError)
    assert 'could not find a configured code for the plugin' in result.output

    code_fleur = generate_code('fleur.fleur').store()
    code_inpgen = generate_code('fleur.inpgen').store()

    # Passing two codes explicitly
    options = ['-S', str(structure.pk), '-X', str(code_fleur.uuid), str(code_inpgen.uuid), '--', 'fleur']
    result = run_cli_command(cmd_relax, options)

    # Passing one code explicitly
    options = ['-S', str(structure.pk), '-X', str(code_fleur.uuid), '--', 'fleur']
    result = run_cli_command(cmd_relax, options)


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
    """Test the `--relax-type` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Test that a non-sensical relax type raises
    options = ['-S', str(structure.pk), '-r', 'cell', 'quantum_espresso']
    result = run_cli_command(cmd_eos, options, raises=click.BadParameter)
    assert "Error: Invalid value for '-r' / '--relax-type': invalid choice: cell. " \
            '(choose from none, atoms, shape, atoms_shape)' in result.output_lines


@pytest.mark.usefixtures('aiida_profile')
@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos(run_cli_command, generate_eos_node, include_magnetization, monkeypatch):
    """Test the `plot_eos` command.

    The default behavior is to plot the result, so we monkeypatch it to do nothing. That functionality is tested
    separately in `tests/common/visialization/test_eos.py.
    """
    from aiida_common_workflows.common.visualization import eos

    def plot_eos(_, __):
        pass

    monkeypatch.setattr(eos, 'plot_eos', plot_eos)

    node = generate_eos_node(include_magnetization=include_magnetization).store()
    options = [str(node.pk)]
    run_cli_command(cmd_plot_eos, options)


@pytest.mark.usefixtures('aiida_profile')
@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos_print_table(run_cli_command, generate_eos_node, include_magnetization, data_regression):
    """Test the `plot_eos` command with the `--print-table` option."""
    node = generate_eos_node(include_magnetization=include_magnetization).store()
    options = [str(node.pk), '--print-table']
    result = run_cli_command(cmd_plot_eos, options)
    data_regression.check({'output_lines': result.output_lines})


@pytest.mark.usefixtures('aiida_profile')
def test_relax_magn_per_type(run_cli_command, generate_structure, generate_code):
    """Test the `--magnetization-per-site` option."""
    structure = generate_structure()
    structure.append_atom(position=(0.000, 0.000, 0.468), symbols=['H'])
    structure.append_atom(position=(0.000, 0.000, 0.268), symbols=['H'])
    structure.store()
    generate_code('quantumespresso.pw').store()

    # Correct
    options = ['-S', str(structure.pk), '--magnetization-per-site', 'str', '--', 'quantum_espresso']
    result = run_cli_command(cmd_relax, options, raises=click.UsageError)
    assert "Error: Invalid value for '--magnetization-per-site': str is not a valid floating point " \
           'value' in result.output
