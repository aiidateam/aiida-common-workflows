# -*- coding: utf-8 -*-
"""Module with utitlies for the CLI."""
import click


def echo_process_results(node):
    """Display a formatted table of the outputs registered for the given process node.

    :param node: the `ProcessNode` of a terminated process.
    """
    from aiida.common.links import LinkType

    class_name = node.process_class.__name__
    outputs = node.get_outgoing(link_type=(LinkType.CREATE, LinkType.RETURN)).all()

    if node.is_finished and node.exit_message:
        state = '{} [{}] `{}`'.format(node.process_state.value, node.exit_status, node.exit_message)
    elif node.is_finished:
        state = '{} [{}]'.format(node.process_state.value, node.exit_status)
    else:
        state = node.process_state.value

    click.echo('{}<{}> terminated with state: {}'.format(class_name, node.pk, state))

    if not outputs:
        click.echo('{}<{}> registered no outputs'.format(class_name, node.pk))
        return

    click.echo('\n{link:25s} {node}'.format(link='Output link', node='Node pk and type'))
    click.echo('{s}'.format(s='-' * 60))

    for triple in sorted(outputs, key=lambda triple: triple.link_label):
        click.echo('{:25s} {}<{}> '.format(triple.link_label, triple.node.__class__.__name__, triple.node.pk))


def launch_process(process, daemon, **inputs):
    """Launch a process with the given inputs.

    If not sent to the daemon, the results will be displayed after the calculation finishes.

    :param process: the process class or process builder.
    :param daemon: boolean, if True will submit to the daemon instead of running in current interpreter.
    :param inputs: inputs for the process if the process is not already a fully prepared builder.
    """
    from aiida.engine import launch, Process, ProcessBuilder

    if isinstance(process, ProcessBuilder):
        process_name = process.process_class.__name__
    elif issubclass(process, Process):
        process_name = process.__name__
    else:
        raise TypeError('invalid type for process: {}'.format(process))

    if daemon:
        node = launch.submit(process, **inputs)
        click.echo('Submitted {}<{}> to the daemon'.format(process_name, node.pk))
    else:
        click.echo('Running a {}...'.format(process_name))
        _, node = launch.run_get_node(process, **inputs)
        echo_process_results(node)
