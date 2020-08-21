# -*- coding: utf-8 -*-
"""Commands to launch common workflows."""
import functools

import click

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
@options.RELAXATION_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.DAEMON()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_relax(plugin, structure, protocol, relaxation_type, threshold_forces, threshold_stress, daemon, show_engines):
    """Relax a crystal structure using the common relax workflow for one of the existing plugin implementations.

    The command will automatically try to find and load the codes that are required by the plugin workflow. If no code
    is installed for at least one of the calculation engines, the command will fail. Use the `--show-engine` flag to
    display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    from aiida.orm import QueryBuilder, Code

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_inputs_generator()

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

    for engine in generator.get_calc_types():
        schema = generator.get_calc_type_schema(engine)
        engines[engine] = {
            'options': {
                'resources': {
                    'num_machines': 1
                },
                'max_wallclock_seconds': 86400,
            }
        }
        code_plugin = schema['code_plugin']
        builder = QueryBuilder().append(Code, filters={'attributes.input_plugin': code_plugin})

        code = builder.first()

        if code is None:
            raise click.UsageError(f'could not find a configured code for the plugin `{code_plugin}`.')

        engines[engine]['code'] = code[0].label

    builder = generator.get_builder(structure, engines, protocol, relaxation_type, threshold_forces, threshold_stress)
    utils.launch_process(builder, daemon)
