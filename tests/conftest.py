# -*- coding: utf-8 -*-
"""Configuration and fixtures for unit test suite."""
import click
import pytest

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']  # pylint: disable=invalid-name


@pytest.fixture
@pytest.mark.usefixtures('aiida_profile')
def with_database():
    """Alias for the `aiida_profile` fixture from `aiida-core`."""
    yield


@pytest.fixture
@pytest.mark.usefixtures('clear_database_before_test')
def clear_database():
    """Alias for the `clear_database_before_test` fixture from `aiida-core`."""
    yield


@pytest.fixture
def run_cli_command():
    """Run a `click` command with the given options.

    The call will raise if the command triggered an exception or the exit code returned is non-zero.
    """
    from click.testing import Result

    def _run_cli_command(command: click.Command, options: list = None, raises: bool = False) -> Result:
        """Run the command and check the result.

        .. note:: the `output_lines` attribute is added to return value containing list of stripped output lines.

        :param options: the list of command line options to pass to the command invocation
        :param raises: whether the command is expected to raise an exception
        :return: test result
        """
        import traceback

        runner = click.testing.CliRunner()
        result = runner.invoke(command, options or [])

        if raises:
            assert result.exception is not None, result.output
            assert result.exit_code != 0
        else:
            assert result.exception is None, ''.join(traceback.format_exception(*result.exc_info))
            assert result.exit_code == 0, result.output

        result.output_lines = [line.strip() for line in result.output.split('\n') if line.strip()]

        return result

    return _run_cli_command


@pytest.fixture
def generate_structure():
    """Generate a `StructureData` node."""

    def _generate_structure():
        from aiida.plugins import DataFactory
        structure = DataFactory('structure')()
        return structure

    return _generate_structure


@pytest.fixture
def generate_code(aiida_localhost):
    """Generate a `Code` node."""

    def _generate_code(entry_point):
        from aiida.plugins import DataFactory
        code = DataFactory('code')(input_plugin_name=entry_point, remote_computer_exec=[aiida_localhost, '/bin/bash'])
        return code

    return _generate_code
