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
@options.STRUCTURE()
@options.CODES()
@options.PROTOCOL(type=click.Choice(['fast', 'moderate', 'precise']), default='fast')
@options.RELAX_TYPE()
@options.ELECTRONIC_TYPE()
@options.SPIN_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.NUMBER_MACHINES()
@options.NUMBER_MPI_PROCS_PER_MACHINE()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@options.REFERENCE_WORKCHAIN()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_relax(  #pylint: disable=too-many-branches
    plugin, structure, codes, protocol, relax_type, electronic_type, spin_type, threshold_forces, threshold_stress,
    number_machines, number_mpi_procs_per_machine, wallclock_seconds, daemon, magnetization_per_site,
    reference_workchain, show_engines
):
    """Relax a crystal structure using the common relax workflow for one of the existing plugin implementations.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.get_engine_types())

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines'
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine'
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
        for engine in generator.get_engine_types():
            schema = generator.get_engine_type_schema(engine)
            click.secho(engine, fg='red', bold=True)
            click.echo('Required code plugin: {}'.format(schema['code_plugin']))
            click.echo('Engine description:   {}'.format(schema['description']))

        return

    engines = {}

    for index, engine in enumerate(generator.get_engine_types()):
        schema = generator.get_engine_type_schema(engine)
        code_plugin = schema['code_plugin']

        code = utils.get_code_from_list_or_database(codes or [], code_plugin)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{code_plugin}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        engines[engine] = {
            'code': code.full_label,
            'options': {
                'resources': {
                    'num_machines': number_machines[index],
                },
                'max_wallclock_seconds': wallclock_seconds[index],
            }
        }

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

    builder = generator.get_builder(
        structure,
        engines,
        protocol=protocol,
        relax_type=relax_type,
        threshold_forces=threshold_forces,
        threshold_stress=threshold_stress,
        electronic_type=electronic_type,
        spin_type=spin_type,
        magnetization_per_site=magnetization_per_site,
        reference_workchain=reference_workchain,
    )
    utils.launch_process(builder, daemon)


@cmd_launch.command('eos')
@click.argument('plugin', type=types.LazyChoice(functools.partial(get_workflow_entry_point_names, 'relax', True)))
@options.STRUCTURE()
@options.CODES()
@options.PROTOCOL(type=click.Choice(['fast', 'moderate', 'precise']), default='fast')
@options.RELAX_TYPE(type=types.LazyChoice(options.get_relax_types_eos))
@options.ELECTRONIC_TYPE()
@options.SPIN_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.NUMBER_MACHINES()
@options.NUMBER_MPI_PROCS_PER_MACHINE()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_eos(  #pylint: disable=too-many-branches
    plugin, structure, codes, protocol, relax_type, electronic_type, spin_type, threshold_forces, threshold_stress,
    number_machines, number_mpi_procs_per_machine, wallclock_seconds, daemon, magnetization_per_site, show_engines
):
    """Compute the equation of state of a crystal structure using the common relax workflow.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.get_engine_types())

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines'
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine'
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
        for engine in generator.get_engine_types():
            schema = generator.get_engine_type_schema(engine)
            click.secho(engine, fg='red', bold=True)
            click.echo('Required code plugin: {}'.format(schema['code_plugin']))
            click.echo('Engine description:   {}'.format(schema['description']))

        return

    engines = {}

    for index, engine in enumerate(generator.get_engine_types()):
        schema = generator.get_engine_type_schema(engine)
        code_plugin = schema['code_plugin']
        code = utils.get_code_from_list_or_database(codes or [], code_plugin)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{code_plugin}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        engines[engine] = {
            'code': code.full_label,
            'options': {
                'resources': {
                    'num_machines': number_machines[index]
                },
                'max_wallclock_seconds': wallclock_seconds[index],
            }
        }

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

    inputs = {
        'structure': structure,
        'generator_inputs': {
            'engines': engines,
            'protocol': protocol,
            'relax_type': relax_type,
            'electronic_type': electronic_type,
            'spin_type': spin_type,
        },
        'sub_process_class': get_entry_point_name_from_class(process_class).name,
    }

    if threshold_forces is not None:
        inputs['generator_inputs']['threshold_forces'] = threshold_forces

    if threshold_stress is not None:
        inputs['generator_inputs']['threshold_stress'] = threshold_stress

    if magnetization_per_site is not None:
        inputs['generator_inputs']['magnetization_per_site'] = magnetization_per_site

    utils.launch_process(EquationOfStateWorkChain, daemon, **inputs)


@cmd_launch.command('dissociation-curve')
@click.argument('plugin', type=types.LazyChoice(functools.partial(get_workflow_entry_point_names, 'relax', True)))
@options.STRUCTURE(default='H2')
@options.CODES()
@options.PROTOCOL(type=click.Choice(['fast', 'moderate', 'precise']), default='fast')
@options.ELECTRONIC_TYPE()
@options.SPIN_TYPE()
@options.NUMBER_MACHINES()
@options.NUMBER_MPI_PROCS_PER_MACHINE()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_dissociation_curve(  #pylint: disable=too-many-branches
    plugin, structure, codes, protocol, electronic_type, spin_type, number_machines, number_mpi_procs_per_machine,
    wallclock_seconds, daemon, magnetization_per_site, show_engines
):
    """Compute the dissociation curve of a diatomic molecule using the common relax workflow.

    The relaxation type is constrained to be `RelaxType.NONE`, meaning a single point calculation.
    It does not make sense to have any other type of relaxation for this task.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """
    # pylint: disable=too-many-locals
    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    from aiida_common_workflows.workflows.dissociation import DissociationCurveWorkChain
    from aiida_common_workflows.workflows.relax.generator import RelaxType

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.get_engine_types())

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines'
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine'
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
        for engine in generator.get_engine_types():
            schema = generator.get_engine_type_schema(engine)
            click.secho(engine, fg='red', bold=True)
            click.echo('Required code plugin: {}'.format(schema['code_plugin']))
            click.echo('Engine description:   {}'.format(schema['description']))

        return

    engines = {}

    for index, engine in enumerate(generator.get_engine_types()):
        schema = generator.get_engine_type_schema(engine)
        code_plugin = schema['code_plugin']

        code = utils.get_code_from_list_or_database(codes or [], code_plugin)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{code_plugin}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        engines[engine] = {
            'code': code.full_label,
            'options': {
                'resources': {
                    'num_machines': number_machines[index]
                },
                'max_wallclock_seconds': wallclock_seconds[index],
            }
        }

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

    inputs = {
        'molecule': structure,
        'generator_inputs': {
            'engines': engines,
            'protocol': protocol,
            'relax_type': RelaxType.NONE,
            'electronic_type': electronic_type,
            'spin_type': spin_type,
        },
        'sub_process_class': get_entry_point_name_from_class(process_class).name,
    }

    if magnetization_per_site is not None:
        inputs['generator_inputs']['magnetization_per_site'] = magnetization_per_site

    utils.launch_process(DissociationCurveWorkChain, daemon, **inputs)


@cmd_launch.command('plot-eos')
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


@cmd_launch.command('plot-dissociation-curve')
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
