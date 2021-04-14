# -*- coding: utf-8 -*-
"""Commands to plot results from a workflow."""

import click

from aiida.cmdline.params import arguments

from .root import cmd_root
from . import options


@cmd_root.group('plot')
def cmd_plot():
    """Plot results from a workflow."""


@cmd_plot.command('eos')
@arguments.NODE()
@options.PRECISIONS()
@options.PRINT_TABLE()
def cmd_plot_eos(node, precisions, print_table):
    """Plot the results from an `EquationOfStateWorkChain`."""
    from tabulate import tabulate

    from aiida.common import LinkType
    from aiida_common_workflows.common.visualization.eos import plot_eos

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

    if print_table:
        headers = ['Volume (Å^3)', 'Energy (eV)', 'Total magnetization (μB)']

        if precisions is not None:
            floatfmt = [f'.{precision}f' for precision in precisions]
            click.echo(tabulate(list(zip(volumes, energies, magnetizations)), headers=headers, floatfmt=floatfmt))
        else:
            click.echo(tabulate(list(zip(volumes, energies, magnetizations)), headers=headers))

    else:
        plot_eos(volumes, energies)


@cmd_plot.command('dissociation-curve')
@arguments.NODE()
@options.PRECISIONS()
@options.PRINT_TABLE()
def cmd_plot_dissociation_curve(node, precisions, print_table):
    """Plot the results from a `DissociationCurveWorkChain`."""

    from tabulate import tabulate

    from aiida.common import LinkType

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

    if print_table:
        headers = ['Distance (Å)', 'Energy (eV)', 'Total magnetization (μB)']

        if precisions is not None:
            floatfmt = [f'.{precision}f' for precision in precisions]
            click.echo(tabulate(list(zip(distances, energies, magnetizations)), headers=headers, floatfmt=floatfmt))
        else:
            click.echo(tabulate(list(zip(distances, energies, magnetizations)), headers=headers))
    else:
        import pylab as plt
        plt.plot(distances, energies, 'o-')
        plt.xlabel('Distance [Å]')
        plt.ylabel('Energy [eV]')
        plt.show()
