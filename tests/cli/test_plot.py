"""Tests for the :mod:`aiida_common_workflows.cli.plot` module."""
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from aiida_common_workflows.cli import plot


@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos(run_cli_command, generate_eos_node, include_magnetization, monkeypatch):
    """Test the `plot_eos` command.

    The default behavior is return a plot, so we monkeypatch it to simply return an empty plot. The plotting
    functionality is tested separately in `tests/common/visialization/test_eos.py.
    """
    from aiida_common_workflows.common.visualization import eos

    def get_eos_plot(_, __):
        return plt

    monkeypatch.setattr(eos, 'get_eos_plot', get_eos_plot)

    node = generate_eos_node(include_magnetization=include_magnetization).store()
    options = [str(node.pk)]
    run_cli_command(plot.cmd_plot_eos, options)


@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos_output_file(run_cli_command, generate_eos_node, include_magnetization, monkeypatch, tmp_path):
    """Test the `plot_eos` command with the `--output-file` option."""
    from aiida_common_workflows.common.visualization import eos

    def get_eos_plot(_, __):
        return plt

    monkeypatch.setattr(eos, 'get_eos_plot', get_eos_plot)

    node = generate_eos_node(include_magnetization=include_magnetization).store()

    output_file = tmp_path / 'plot.png'
    options = [str(node.pk), '--output-file', str(output_file)]
    result = run_cli_command(plot.cmd_plot_eos, options)
    assert f'Success: Plot saved to {output_file}' in result.output
    assert Path.exists(output_file)


@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos_print_table(run_cli_command, generate_eos_node, include_magnetization, data_regression):
    """Test the `plot_eos` command with the `--print-table` option."""
    node = generate_eos_node(include_magnetization=include_magnetization).store()
    options = [str(node.pk), '--print-table']
    result = run_cli_command(plot.cmd_plot_eos, options)
    data_regression.check({'output_lines': result.output_lines})


@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos_print_table_output_file(run_cli_command, generate_eos_node, include_magnetization, tmp_path):
    """Test the `plot_eos` command with the `--print-table` and `--output-file` options."""
    node = generate_eos_node(include_magnetization=include_magnetization).store()

    output_file = tmp_path / 'table.txt'
    options = [str(node.pk), '--print-table', '--output-file', str(output_file)]

    result = run_cli_command(plot.cmd_plot_eos, options)
    assert f'Success: Table saved to {output_file}' in result.output
    assert Path.exists(output_file)


@pytest.mark.parametrize('precisions', ((8,), (8, 7), (8, 7, 6), (8, 7, 6, 5)))
def test_plot_eos_precision(run_cli_command, generate_eos_node, precisions, data_regression):
    """Test the `plot_eos` command with the `--precisions` option.

    The command should work even if too many or too few values are specified. If too few are specified, the default is
    used for the remaining columns. If there are too many, the surplus is simply ignored.
    """
    node = generate_eos_node().store()
    options = [str(node.pk), '--print-table', '--precisions'] + [str(p) for p in precisions]
    result = run_cli_command(plot.cmd_plot_eos, options)
    data_regression.check({'output_lines': result.output_lines})


def test_plot_eos_wrong_workchain(run_cli_command, generate_dissociation_curve_node):
    """Test the `plot_eos` command in case the provided work chain is incorrect."""
    node = generate_dissociation_curve_node().store()

    options = [str(node.pk)]
    result = run_cli_command(plot.cmd_plot_eos, options, raises=SystemExit)
    assert 'does not correspond to an EquationOfStateWorkChain' in result.output


def test_plot_eos_missing_outputs(run_cli_command, generate_eos_node):
    """Test the `plot_eos` command in case the provided work chain is missing outputs."""
    node = generate_eos_node(include_energy=False).store()

    options = [str(node.pk)]
    result = run_cli_command(plot.cmd_plot_eos, options, raises=SystemExit)
    assert "is missing required outputs: ('total_energies',)" in result.output


def test_plot_dissociation_curve(run_cli_command, generate_dissociation_curve_node, monkeypatch):
    """Test the `plot_dissociation_curve` command.

    The default behavior is return a plot, so we monkeypatch it to simply return an empty plot. The functionality is
    tested separately in `tests/common/visialization/test_dissociation.py.
    """
    from aiida_common_workflows.common.visualization import dissociation

    def get_dissociation_plot(_, __):
        return plt

    monkeypatch.setattr(dissociation, 'get_dissociation_plot', get_dissociation_plot)

    node = generate_dissociation_curve_node().store()
    options = [str(node.pk)]
    run_cli_command(plot.cmd_plot_dissociation_curve, options)


@pytest.mark.parametrize('precisions', ((8, 7),))
def test_plot_dissociation_curve_print_table(
    run_cli_command, generate_dissociation_curve_node, precisions, data_regression
):
    """Test the `plot_dissociation_curve` command with the `--print-table` and `--precisions` options.

    The command should work even if too many or too few values are specified. If too few are specified, the default is
    used for the remaining columns. If there are too many, the surplus is simply ignored. These variants are tested in
    ``test_plot_eos_precision``. Here we only test one version to prevent creation of too many test comparison files.
    """
    node = generate_dissociation_curve_node().store()
    options = [str(node.pk), '--print-table', '--precisions'] + [str(p) for p in precisions]
    result = run_cli_command(plot.cmd_plot_dissociation_curve, options)
    data_regression.check({'output_lines': result.output_lines})


def test_plot_dissociation_curve_output_file(run_cli_command, generate_dissociation_curve_node, monkeypatch, tmp_path):
    """Test the `plot_dissociation_curve` command with the `--output-file` option."""
    from aiida_common_workflows.common.visualization import dissociation

    def get_dissociation_plot(_, __):
        return plt

    monkeypatch.setattr(dissociation, 'get_dissociation_plot', get_dissociation_plot)

    node = generate_dissociation_curve_node().store()
    output_file = tmp_path / 'plot.png'
    options = [str(node.pk), '--output-file', str(output_file)]

    result = run_cli_command(plot.cmd_plot_dissociation_curve, options)
    assert f'Success: Plot saved to {output_file}' in result.output
    assert Path.exists(output_file)


def test_plot_dissociation_curve_print_table_output_file(run_cli_command, generate_dissociation_curve_node, tmp_path):
    """Test the `plot_dissociation_curve` command with the `--output-file` option."""
    node = generate_dissociation_curve_node().store()

    output_file = tmp_path / 'table.txt'
    options = [str(node.pk), '--print-table', '--output-file', str(output_file)]

    result = run_cli_command(plot.cmd_plot_dissociation_curve, options)
    assert f'Success: Table saved to {output_file}' in result.output
    assert Path.exists(output_file)


def test_plot_dissociation_curve_wrong_workchain(run_cli_command, generate_eos_node):
    """Test the `plot_dissociation_curve` command in case the provided work chain is incorrect."""
    node = generate_eos_node().store()

    options = [str(node.pk)]
    result = run_cli_command(plot.cmd_plot_dissociation_curve, options, raises=SystemExit)
    assert 'does not correspond to a DissociationCurveWorkChain' in result.output


def test_plot_dissociation_curve_missing_outputs(run_cli_command, generate_dissociation_curve_node):
    """Test the `plot_dissociation_curve` command in case the provided work chain is missing outputs."""
    node = generate_dissociation_curve_node(include_energy=False).store()

    options = [str(node.pk)]
    result = run_cli_command(plot.cmd_plot_dissociation_curve, options, raises=SystemExit)
    assert "is missing required outputs: ('total_energies',)" in result.output
