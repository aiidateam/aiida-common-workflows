# -*- coding: utf-8 -*-
"""Commands to plot results from a workflow."""

import click

from aiida.cmdline.params import arguments
from aiida.cmdline.utils import echo

from .root import cmd_root
from . import options


@cmd_root.group('plot')
def cmd_plot():
    """Plot results from a workflow."""


@cmd_plot.command('eos')
@arguments.NODE()
@options.PRECISIONS()
@options.PRINT_TABLE()
@options.OUTPUT_FILENAME()
def cmd_plot_eos(node, precisions, print_table, output_filename):
    """Plot the results from an `EquationOfStateWorkChain`."""
    # pylint: disable=too-many-locals
    from tabulate import tabulate

    from aiida.common import LinkType
    from aiida_common_workflows.common.visualization.eos import get_eos_plot

    outputs = node.get_outgoing(link_type=LinkType.RETURN).nested()

    volumes = []
    energies = []
    magnetizations = []

    for index, structure in sorted(outputs['structures'].items()):
        volumes.append(structure.get_cell_volume())
        energies.append(outputs['total_energies'][index].value)

        try:
            total_magnetization = outputs['total_magnetizations'][index].value
        except KeyError:
            total_magnetization = None

        magnetizations.append(total_magnetization)

    # Sort the results by volumes
    energies = [e for _, e in sorted(zip(volumes, energies))]
    magnetizations = [m for _, m in sorted(zip(volumes, magnetizations))]
    volumes = sorted(volumes)

    if print_table:
        tabulate_inputs = {
            'tabular_data': list(zip(volumes, energies, magnetizations)),
            'headers': ['Volume (Å^3)', 'Energy (eV)', 'Total magnetization (μB)']
        }

        if precisions is not None:
            tabulate_inputs['floatfmt'] = [f'.{precision}f' for precision in precisions]

        output = tabulate(**tabulate_inputs)

        if output_filename is not None:
            with click.open_file(output_filename, 'w') as file:
                file.write(output)
            echo.echo_success(f'Table saved to {output_filename}')
        else:
            click.echo(output)
    else:
        eos_plot = get_eos_plot(volumes, energies)

        if output_filename is not None:
            eos_plot.savefig(output_filename)
            output_filename = f'{output_filename}.png' if len(output_filename.split('.')) == 1 else output_filename
            echo.echo_success(f'Plot saved to {output_filename}')
        else:
            eos_plot.show()


@cmd_plot.command('dissociation-curve')
@arguments.NODE()
@options.PRECISIONS()
@options.PRINT_TABLE()
@options.OUTPUT_FILENAME()
def cmd_plot_dissociation_curve(node, precisions, print_table, output_filename):
    """Plot the results from a `DissociationCurveWorkChain`."""
    # pylint: disable=too-many-locals
    from tabulate import tabulate
    from aiida.common import LinkType
    from aiida_common_workflows.common.visualization.dissociation import get_dissociation_plot

    outputs = node.get_outgoing(link_type=LinkType.RETURN).nested()

    distances = []
    energies = []
    magnetizations = []

    for index in outputs['total_energies'].keys():
        distances.append(outputs['distances'][index].value)
        energies.append(outputs['total_energies'][index].value)

        try:
            total_magnetization = outputs['total_magnetizations'][index].value
        except KeyError:
            total_magnetization = None

        magnetizations.append(total_magnetization)

    # Sort the results by distance
    energies = [e for _, e in sorted(zip(distances, energies))]
    magnetizations = [m for _, m in sorted(zip(distances, magnetizations))]
    distances = sorted(distances)

    if print_table:
        tabulate_inputs = {
            'tabular_data': list(zip(distances, energies, magnetizations)),
            'headers': ['Distance (Å)', 'Energy (eV)', 'Total magnetization (μB)']
        }

        if precisions is not None:
            tabulate_inputs['floatfmt'] = [f'.{precision}f' for precision in precisions]

        output = tabulate(**tabulate_inputs)

        if output_filename is not None:
            with click.open_file(output_filename, 'w') as file:
                file.write(output)
            echo.echo_success(f'Table saved to {output_filename}')
        else:
            click.echo(output)
    else:
        dissociation_plot = get_dissociation_plot(distances, energies)

        if output_filename is not None:
            dissociation_plot.savefig(output_filename)
            output_filename = f'{output_filename}.png' if len(output_filename.split('.')) == 1 else output_filename
            echo.echo_success(f'Plot saved to {output_filename}')
        else:
            dissociation_plot.show()
