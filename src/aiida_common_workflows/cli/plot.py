"""Commands to plot results from a workflow."""
import click
from aiida.cmdline.params import arguments
from aiida.cmdline.utils import echo
from aiida.plugins import WorkflowFactory

from . import options
from .root import cmd_root

EquationOfStateWorkChain = WorkflowFactory('common_workflows.eos')
DissociationCurveWorkChain = WorkflowFactory('common_workflows.dissociation_curve')


@cmd_root.group('plot')
def cmd_plot():
    """Plot results from a workflow."""


@cmd_plot.command('eos')
@arguments.WORKFLOW()
@options.PRECISIONS()
@options.PRINT_TABLE()
@options.OUTPUT_FILE()
def cmd_plot_eos(workflow, precisions, print_table, output_file):
    """Plot the results from an `EquationOfStateWorkChain`."""

    from aiida.common import LinkType
    from tabulate import tabulate

    from aiida_common_workflows.common.visualization.eos import get_eos_plot

    if workflow.process_class is not EquationOfStateWorkChain:
        echo.echo_critical(
            f'node {workflow.__class__.__name__}<{workflow.pk}> does not correspond to an EquationOfStateWorkChain.'
        )
    outputs = workflow.base.links.get_outgoing(link_type=LinkType.RETURN).nested()

    missing_outputs = tuple(output for output in ('structures', 'total_energies') if output not in outputs)
    if missing_outputs:
        echo.echo_critical(
            f'node {workflow.__class__.__name__}<{workflow.pk}> is missing required outputs: {missing_outputs}'
        )

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
            'headers': ['Volume (Å^3)', 'Energy (eV)', 'Total magnetization (μB)'],
        }

        if precisions is not None:
            tabulate_inputs['floatfmt'] = [f'.{precision}f' for precision in precisions]

        output = tabulate(**tabulate_inputs)

        if output_file is not None:
            with click.open_file(output_file, 'w') as file:
                file.write(output)
            echo.echo_success(f'Table saved to {output_file}')
        else:
            click.echo(output)
    else:
        eos_plot = get_eos_plot(volumes, energies)

        if output_file is not None:
            eos_plot.savefig(output_file)
            output_file = f'{output_file}.png' if len(output_file.split('.')) == 1 else output_file
            echo.echo_success(f'Plot saved to {output_file}')
        else:
            eos_plot.show()


@cmd_plot.command('dissociation-curve')
@arguments.WORKFLOW()
@options.PRECISIONS()
@options.PRINT_TABLE()
@options.OUTPUT_FILE()
def cmd_plot_dissociation_curve(workflow, precisions, print_table, output_file):
    """Plot the results from a `DissociationCurveWorkChain`."""

    from aiida.common import LinkType
    from tabulate import tabulate

    from aiida_common_workflows.common.visualization.dissociation import get_dissociation_plot

    if workflow.process_class is not DissociationCurveWorkChain:
        echo.echo_critical(
            f'node {workflow.__class__.__name__}<{workflow.pk}> does not correspond to a DissociationCurveWorkChain.'
        )
    outputs = workflow.base.links.get_outgoing(link_type=LinkType.RETURN).nested()

    missing_outputs = tuple(output for output in ('distances', 'total_energies') if output not in outputs)
    if missing_outputs:
        echo.echo_critical(
            f'node {workflow.__class__.__name__}<{workflow.pk}> is missing required outputs: {missing_outputs}'
        )

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
            'headers': ['Distance (Å)', 'Energy (eV)', 'Total magnetization (μB)'],
        }

        if precisions is not None:
            tabulate_inputs['floatfmt'] = [f'.{precision}f' for precision in precisions]

        output = tabulate(**tabulate_inputs)

        if output_file is not None:
            with click.open_file(output_file, 'w') as file:
                file.write(output)
            echo.echo_success(f'Table saved to {output_file}')
        else:
            click.echo(output)
    else:
        dissociation_plot = get_dissociation_plot(distances, energies)

        if output_file is not None:
            dissociation_plot.savefig(output_file)
            output_filename = f'{output_file}.png' if len(output_file.split('.')) == 1 else output_file
            echo.echo_success(f'Plot saved to {output_filename}')
        else:
            dissociation_plot.show()
