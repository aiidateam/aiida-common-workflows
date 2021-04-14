# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.cli.plot` module."""
import pytest

from aiida_common_workflows.cli import plot


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
    run_cli_command(plot.cmd_plot_eos, options)


@pytest.mark.usefixtures('aiida_profile')
@pytest.mark.parametrize('include_magnetization', (True, False))
def test_plot_eos_print_table(run_cli_command, generate_eos_node, include_magnetization, data_regression):
    """Test the `plot_eos` command with the `--print-table` option."""
    node = generate_eos_node(include_magnetization=include_magnetization).store()
    options = [str(node.pk), '--print-table']
    result = run_cli_command(plot.cmd_plot_eos, options)
    data_regression.check({'output_lines': result.output_lines})


@pytest.mark.usefixtures('aiida_profile')
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


@pytest.mark.usefixtures('aiida_profile')
@pytest.mark.parametrize('precisions', ((8, 7),))
def test_plot_dissociation_curve(run_cli_command, generate_dissociation_curve_node, precisions, data_regression):
    """Test the `plot_dissociation_curve` command with the `--precisions` option.

    The command should work even if too many or too few values are specified. If too few are specified, the default is
    used for the remaining columns. If there are too many, the surplus is simply ignored. These variants are tested in
    ``test_plot_eos_precision``. Here we only test one version to prevent creation of too many test comparison files.
    """
    node = generate_dissociation_curve_node().store()
    options = [str(node.pk), '--print-table', '--precisions'] + [str(p) for p in precisions]
    result = run_cli_command(plot.cmd_plot_dissociation_curve, options)
    data_regression.check({'output_lines': result.output_lines})
