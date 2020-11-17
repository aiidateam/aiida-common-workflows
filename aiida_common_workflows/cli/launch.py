# -*- coding: utf-8 -*-
"""Commands to launch common workflows."""
import functools

import click

from aiida.cmdline.params import arguments
from aiida.cmdline.params import types

from aiida_common_workflows.plugins import get_workflow_entry_point_names, load_workflow_entry_point
from .root import cmd_root
from . import options
from . import utils


@cmd_root.group('launch')
def cmd_launch():
    """Launch a common workflow."""


@cmd_launch.command('relax')
@click.argument('plugin', type=types.LazyChoice(functools.partial(get_workflow_entry_point_names, 'relax', True)))
@options.STRUCTURE(help='The structure to relax.')
@options.PROTOCOL(type=click.Choice(['fast', 'moderate', 'precise']), default='fast')
@options.RELAX_TYPE()
@options.SPIN_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.NUMBER_MACHINES()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_relax(
    plugin, structure, protocol, relax_type, spin_type, threshold_forces, threshold_stress, number_machines,
    wallclock_seconds, daemon, show_engines
):
    """Relax a crystal structure using the common relax workflow for one of the existing plugin implementations.

    The command will automatically try to find and load the codes that are required by the plugin workflow. If no code
    is installed for at least one of the calculation engines, the command will fail. Use the `--show-engine` flag to
    display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    from aiida.orm import QueryBuilder, Code

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_inputs_generator()

    number_engines = len(generator.get_calc_types())

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines'
        )

    if wallclock_seconds is None:
        wallclock_seconds = [1 * 3600] * number_engines

    if len(wallclock_seconds) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--wallclock-seconds'
        )

    if not generator.is_valid_protocol(protocol):
        protocols = generator.get_protocol_names()
        process_class_name = process_class.__name__
        message = f'`{protocol}` is not implemented by `{process_class_name}` workflow: choose one of {protocols}'
        raise click.BadParameter(message, param_hint='protocol')

    if show_engines:
        for engine in generator.get_calc_types():
            schema = generator.get_calc_type_schema(engine)
            click.secho(engine, fg='red', bold=True)
            click.echo('Required code plugin: {}'.format(schema['code_plugin']))
            click.echo('Engine description:   {}'.format(schema['description']))

        return

    engines = {}

    for index, engine in enumerate(generator.get_calc_types()):
        schema = generator.get_calc_type_schema(engine)
        engines[engine] = {
            'options': {
                'resources': {
                    'num_machines': number_machines[index]
                },
                'max_wallclock_seconds': wallclock_seconds[index],
            }
        }
        code_plugin = schema['code_plugin']
        query = QueryBuilder().append(Code, filters={'attributes.input_plugin': code_plugin})

        code = query.first()

        if code is None:
            raise click.UsageError(f'could not find a configured code for the plugin `{code_plugin}`.')

        engines[engine]['code'] = code[0].full_label

    builder = generator.get_builder(
        structure,
        engines,
        protocol=protocol,
        relax_type=relax_type,
        threshold_forces=threshold_forces,
        threshold_stress=threshold_stress,
        spin_type=spin_type
    )
    utils.launch_process(builder, daemon)


@cmd_launch.command('eos')
@click.argument('plugin', type=types.LazyChoice(functools.partial(get_workflow_entry_point_names, 'relax', True)))
@options.STRUCTURE(help='The structure to relax.')
@options.PROTOCOL(type=click.Choice(['fast', 'moderate', 'precise']), default='fast')
@options.RELAX_TYPE(type=types.LazyChoice(options.get_relax_types_eos))
@options.SPIN_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.NUMBER_MACHINES()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_eos(
    plugin, structure, protocol, relax_type, spin_type, threshold_forces, threshold_stress, number_machines,
    wallclock_seconds, daemon, show_engines
):
    """Compute the equation of state of a crystal structure using the common relax workflow.

    The command will automatically try to find and load the codes that are required by the plugin workflow. If no code
    is installed for at least one of the calculation engines, the command will fail. Use the `--show-engine` flag to
    display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    from aiida.orm import QueryBuilder, Code
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_inputs_generator()

    number_engines = len(generator.get_calc_types())

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines'
        )

    if wallclock_seconds is None:
        wallclock_seconds = [1 * 3600] * number_engines

    if len(wallclock_seconds) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--wallclock-seconds'
        )

    if not generator.is_valid_protocol(protocol):
        protocols = generator.get_protocol_names()
        process_class_name = process_class.__name__
        message = f'`{protocol}` is not implemented by `{process_class_name}` workflow: choose one of {protocols}'
        raise click.BadParameter(message, param_hint='protocol')

    if show_engines:
        for engine in generator.get_calc_types():
            schema = generator.get_calc_type_schema(engine)
            click.secho(engine, fg='red', bold=True)
            click.echo('Required code plugin: {}'.format(schema['code_plugin']))
            click.echo('Engine description:   {}'.format(schema['description']))

        return

    engines = {}

    for index, engine in enumerate(generator.get_calc_types()):
        schema = generator.get_calc_type_schema(engine)
        engines[engine] = {
            'options': {
                'resources': {
                    'num_machines': number_machines[index]
                },
                'max_wallclock_seconds': wallclock_seconds[index],
            }
        }
        code_plugin = schema['code_plugin']
        query = QueryBuilder().append(Code, filters={'attributes.input_plugin': code_plugin})

        code = query.first()

        if code is None:
            raise click.UsageError(f'could not find a configured code for the plugin `{code_plugin}`.')

        engines[engine]['code'] = code[0].full_label

    inputs = {
        'structure': structure,
        'generator_inputs': {
            'calc_engines': engines,
            'protocol': protocol,
            'relax_type': relax_type,
            'spin_type': spin_type,
        },
        'sub_process_class': get_entry_point_name_from_class(process_class).name,
    }

    if threshold_forces is not None:
        inputs['generator_inputs']['threshold_forces'] = threshold_forces

    if threshold_stress is not None:
        inputs['generator_inputs']['threshold_stress'] = threshold_stress

    utils.launch_process(EquationOfStateWorkChain, daemon, **inputs)


@cmd_launch.command('plot-eos')
@arguments.NODE()
def cmd_plot_eos(node):
    """Plot the results from an `EquationOfStateWorkChain`."""
    from aiida.common import LinkType
    from aiida_common_workflows.common.visualization.eos import plot_eos

    outputs = node.get_outgoing(link_type=LinkType.RETURN).nested()

    volumes = []
    energies = []

    for index, structure in sorted(outputs['structures'].items()):
        volumes.append(structure.get_cell_volume())
        energies.append(outputs['total_energies'][index].value)

    plot_eos(volumes, energies)
