"""Commands to launch common workflows."""
import functools

import click
from aiida.cmdline.params import types

from aiida_common_workflows.plugins import get_workflow_entry_point_names, load_workflow_entry_point

from . import options, utils
from .root import cmd_root


def validate_engine_options(engine_options, all_engines):
    """Validate the custom engine_options.

    It will check the type (dictionary) and if there are unknown engine types.

    :param engine_options: the engine_options returned from the command line option `options.ENGINE_OPTIONS`.
    :param all_engines: a list of valid engine names
    :raises click.BadParameter: if the options do not validate.
    """
    if not isinstance(engine_options, dict):
        message = f'You must pass a dictionary in JSON format (it is now {type(engine_options)}'
        raise click.BadParameter(message, param_hint='engine-options')

    unknown_engines = set(engine_options).difference(all_engines)
    if unknown_engines:
        message = f'You are passing unknown engine types: {unknown_engines}'
        raise click.BadParameter(message, param_hint='engine-options')


@cmd_root.group('launch')
def cmd_launch():
    """Launch a common workflow."""


@cmd_launch.command('relax')
@click.argument('plugin', type=types.LazyChoice(functools.partial(get_workflow_entry_point_names, 'relax', True)))
@options.STRUCTURE()
@options.CODES()
@options.PROTOCOL(
    type=click.Choice(['fast', 'moderate', 'precise', 'verification-PBE-v1', 'verification-PBE-v1-sirius']),
    default='fast',
)
@options.RELAX_TYPE()
@options.ELECTRONIC_TYPE()
@options.SPIN_TYPE()
@options.THRESHOLD_FORCES()
@options.THRESHOLD_STRESS()
@options.NUMBER_MACHINES()
@options.NUMBER_MPI_PROCS_PER_MACHINE()
@options.NUMBER_CORES_PER_MPIPROC()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@options.REFERENCE_WORKCHAIN()
@options.ENGINE_OPTIONS()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_relax(  # noqa: PLR0912,PLR0913,PLR0915
    plugin,
    structure,
    codes,
    protocol,
    relax_type,
    electronic_type,
    spin_type,
    threshold_forces,
    threshold_stress,
    number_machines,
    number_mpi_procs_per_machine,
    number_cores_per_mpiproc,
    wallclock_seconds,
    daemon,
    magnetization_per_site,
    reference_workchain,
    engine_options,
    show_engines,
):
    """Relax a crystal structure using the common relax workflow for one of the existing plugin implementations.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.spec().inputs['engines'])

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines',
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine',
        )

    if number_cores_per_mpiproc is not None and len(number_cores_per_mpiproc) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-cores-per-mpiproc',
        )

    if wallclock_seconds is None:
        wallclock_seconds = [1 * 3600] * number_engines

    if len(wallclock_seconds) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--wallclock-seconds',
        )

    if not generator.is_valid_protocol(protocol):
        protocols = generator.get_protocol_names()
        process_class_name = process_class.__name__
        message = f'`{protocol}` is not implemented by `{process_class_name}` workflow: choose one of {protocols}'
        raise click.BadParameter(message, param_hint='protocol')

    if show_engines:
        for engine, port in generator.spec().inputs['engines'].items():
            click.secho(engine, fg='red', bold=True)
            click.echo(f'Required code plugin: {port["code"].entry_point}')
            click.echo(f'Engine description:   {port.help}')

        return

    validate_engine_options(engine_options, generator.spec().inputs['engines'])

    engines = {}

    for index, engine in enumerate(generator.spec().inputs['engines']):
        port = generator.spec().inputs['engines'][engine]
        entry_point = port['code'].code_entry_point
        code = utils.get_code_from_list_or_database(codes or [], entry_point)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{entry_point}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        all_options = {
            'resources': {
                'num_machines': number_machines[index],
            },
            'max_wallclock_seconds': wallclock_seconds[index],
        }
        all_options.update(engine_options.get(engine, {}))

        engines[engine] = {'code': code.full_label, 'options': all_options}

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

        if number_cores_per_mpiproc is not None:
            engines[engine]['options']['resources']['num_cores_per_mpiproc'] = number_cores_per_mpiproc[index]

    inputs = {
        'structure': structure,
        'engines': engines,
        'protocol': protocol,
        'spin_type': spin_type,
        'relax_type': relax_type,
        'electronic_type': electronic_type,
    }

    if threshold_forces is not None:
        inputs['threshold_forces'] = threshold_forces

    if threshold_stress is not None:
        inputs['threshold_stress'] = threshold_stress

    if magnetization_per_site is not None:
        inputs['magnetization_per_site'] = magnetization_per_site

    if reference_workchain is not None:
        inputs['reference_workchain'] = reference_workchain

    builder = generator.get_builder(**inputs)
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
@options.NUMBER_CORES_PER_MPIPROC()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@options.ENGINE_OPTIONS()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_eos(  # noqa: PLR0912,PLR0913,PLR0915
    plugin,
    structure,
    codes,
    protocol,
    relax_type,
    electronic_type,
    spin_type,
    threshold_forces,
    threshold_stress,
    number_machines,
    number_mpi_procs_per_machine,
    number_cores_per_mpiproc,
    wallclock_seconds,
    daemon,
    magnetization_per_site,
    engine_options,
    show_engines,
):
    """Compute the equation of state of a crystal structure using the common relax workflow.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """

    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.spec().inputs['engines'])

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines',
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine',
        )

    if number_cores_per_mpiproc is not None and len(number_cores_per_mpiproc) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-cores-per-mpiproc',
        )

    if wallclock_seconds is None:
        wallclock_seconds = [1 * 3600] * number_engines

    if len(wallclock_seconds) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--wallclock-seconds',
        )

    if not generator.is_valid_protocol(protocol):
        protocols = generator.get_protocol_names()
        process_class_name = process_class.__name__
        message = f'`{protocol}` is not implemented by `{process_class_name}` workflow: choose one of {protocols}'
        raise click.BadParameter(message, param_hint='protocol')

    if show_engines:
        for engine, port in generator.spec().inputs['engines'].items():
            click.secho(engine, fg='red', bold=True)
            click.echo(f'Required code plugin: {port["code"].entry_point}')
            click.echo(f'Engine description:   {port.help}')

        return

    validate_engine_options(engine_options, generator.spec().inputs['engines'])

    engines = {}

    for index, engine in enumerate(generator.spec().inputs['engines']):
        port = generator.spec().inputs['engines'][engine]
        entry_point = port['code'].code_entry_point
        code = utils.get_code_from_list_or_database(codes or [], entry_point)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{entry_point}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        all_options = {
            'resources': {
                'num_machines': number_machines[index],
            },
            'max_wallclock_seconds': wallclock_seconds[index],
        }
        all_options.update(engine_options.get(engine, {}))

        engines[engine] = {'code': code.full_label, 'options': all_options}

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

        if number_cores_per_mpiproc is not None:
            engines[engine]['options']['resources']['num_cores_per_mpiproc'] = number_cores_per_mpiproc[index]

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
@options.NUMBER_CORES_PER_MPIPROC()
@options.WALLCLOCK_SECONDS()
@options.DAEMON()
@options.MAGNETIZATION_PER_SITE()
@options.ENGINE_OPTIONS()
@click.option('--show-engines', is_flag=True, help='Show information on the required calculation engines.')
def cmd_dissociation_curve(  # noqa: PLR0912, PLR0913
    plugin,
    structure,
    codes,
    protocol,
    electronic_type,
    spin_type,
    number_machines,
    number_mpi_procs_per_machine,
    number_cores_per_mpiproc,
    wallclock_seconds,
    daemon,
    magnetization_per_site,
    engine_options,
    show_engines,
):
    """Compute the dissociation curve of a diatomic molecule using the common relax workflow.

    The relaxation type is constrained to be `RelaxType.NONE`, meaning a single point calculation.
    It does not make sense to have any other type of relaxation for this task.

    The codes required for the plugin workflow in order to complete the task can be passed with the option `-X`,
    however, if no code is passed, the command will automatically try to find and load the codes that are required.
    If no code is installed for at least one of the calculation engines, the command will fail.
    Use the `--show-engine` flag to display the required calculation engines for the selected plugin workflow.
    """

    from aiida_common_workflows.plugins import get_entry_point_name_from_class
    from aiida_common_workflows.workflows.dissociation import DissociationCurveWorkChain
    from aiida_common_workflows.workflows.relax.generator import RelaxType

    process_class = load_workflow_entry_point('relax', plugin)
    generator = process_class.get_input_generator()

    number_engines = len(generator.spec().inputs['engines'])

    if number_machines is None:
        number_machines = [1] * number_engines

    if len(number_machines) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-machines',
        )

    if number_mpi_procs_per_machine is not None and len(number_mpi_procs_per_machine) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-mpi-procs-per-machine',
        )

    if number_cores_per_mpiproc is not None and len(number_cores_per_mpiproc) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--number-cores-per-mpiproc',
        )

    if wallclock_seconds is None:
        wallclock_seconds = [1 * 3600] * number_engines

    if len(wallclock_seconds) != number_engines:
        raise click.BadParameter(
            f'{process_class.__name__} has {number_engines} engine steps, so requires {number_engines} values',
            param_hint='--wallclock-seconds',
        )

    if not generator.is_valid_protocol(protocol):
        protocols = generator.get_protocol_names()
        process_class_name = process_class.__name__
        message = f'`{protocol}` is not implemented by `{process_class_name}` workflow: choose one of {protocols}'
        raise click.BadParameter(message, param_hint='protocol')

    if show_engines:
        for engine, port in generator.spec().inputs['engines'].items():
            click.secho(engine, fg='red', bold=True)
            click.echo(f'Required code plugin: {port["code"].entry_point}')
            click.echo(f'Engine description:   {port.help}')

        return

    validate_engine_options(engine_options, generator.spec().inputs['engines'].keys())

    engines = {}

    for index, engine in enumerate(generator.spec().inputs['engines']):
        port = generator.spec().inputs['engines'][engine]
        entry_point = port['code'].code_entry_point
        code = utils.get_code_from_list_or_database(codes or [], entry_point)

        if code is None:
            raise click.UsageError(
                f'could not find a configured code for the plugin `{entry_point}`. '
                'Either provide it with the -X option or make sure such a code is configured in the DB.'
            )

        all_options = {
            'resources': {
                'num_machines': number_machines[index],
            },
            'max_wallclock_seconds': wallclock_seconds[index],
        }
        all_options.update(engine_options.get(engine, {}))

        engines[engine] = {'code': code.full_label, 'options': all_options}

        if number_mpi_procs_per_machine is not None:
            engines[engine]['options']['resources']['num_mpiprocs_per_machine'] = number_mpi_procs_per_machine[index]
            if number_mpi_procs_per_machine[index] > 1:
                engines[engine]['options']['withmpi'] = True

        if number_cores_per_mpiproc is not None:
            engines[engine]['options']['resources']['num_cores_per_mpiproc'] = number_cores_per_mpiproc[index]

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
