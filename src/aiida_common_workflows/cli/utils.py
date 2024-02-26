"""Module with utitlies for the CLI."""
import sys

import click


def echo_process_results(node):
    """Display a formatted table of the outputs registered for the given process node.

    If the node corresponds to a process that was actually run and that did not finish with a zero exit code, this
    function will call ``sys.exit(1)``.

    :param node: the `ProcessNode` of a terminated process.
    """
    from aiida.common.links import LinkType

    class_name = node.process_class.__name__
    outputs = node.base.links.get_outgoing(link_type=(LinkType.CREATE, LinkType.RETURN)).all()

    if node.is_finished and node.exit_message:
        state = f'{node.process_state.value} [{node.exit_status}] `{node.exit_message}`'
    elif node.is_finished:
        state = f'{node.process_state.value} [{node.exit_status}]'
    else:
        state = node.process_state.value

    click.echo(f'{class_name}<{node.pk}> terminated with state: {state}')

    if not outputs:
        click.echo(f'{class_name}<{node.pk}> registered no outputs')
        return

    click.echo(f"\n{'Output link':25s} Node pk and type")
    click.echo(f"{'-' * 60}")

    for triple in sorted(outputs, key=lambda triple: triple.link_label):
        click.echo(f'{triple.link_label:25s} {triple.node.__class__.__name__}<{triple.node.pk}> ')

    if not node.is_finished_ok:
        sys.exit(1)


def launch_process(process, daemon, **inputs):
    """Launch a process with the given inputs.

    If not sent to the daemon, the results will be displayed after the calculation finishes.

    :param process: the process class or process builder.
    :param daemon: boolean, if True will submit to the daemon instead of running in current interpreter.
    :param inputs: inputs for the process if the process is not already a fully prepared builder.
    """
    from aiida.engine import Process, ProcessBuilder, launch

    if isinstance(process, ProcessBuilder):
        process_name = process.process_class.__name__
    elif issubclass(process, Process):
        process_name = process.__name__
    else:
        raise TypeError(f'invalid type for process: {process}')

    if daemon:
        node = launch.submit(process, **inputs)
        click.echo(f'Submitted {process_name}<{node.pk}> to the daemon')
    else:
        click.echo(f'Running a {process_name}...')
        _, node = launch.run_get_node(process, **inputs)
        echo_process_results(node)


def get_code_from_list_or_database(codes, entry_point: str):
    """Return a code that is configured for the given calculation job entry point.

    First the list of ``Code`` instances is scanned for a suitable code and if not found, one is attempted to be loaded
    from the database. If no codes are found, ``None`` is returned.

    :param codes: list of aiida `Code` nodes.
    :param entry_point: calculation job entry point name.
    :return: a ``Code`` instance configured for the given entry point or ``None``.
    """
    from aiida.orm import InstalledCode, QueryBuilder

    for entry in codes:
        if entry.default_calc_job_plugin == entry_point:
            return entry

    result = QueryBuilder().append(InstalledCode, filters={'attributes.input_plugin': entry_point}).first()

    if result is not None:
        return result[0]

    return None
