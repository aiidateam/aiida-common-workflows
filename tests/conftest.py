# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Configuration and fixtures for unit test suite."""
import os
import tempfile

import click
import pytest

from aiida.common.constants import elements

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']  # pylint: disable=invalid-name


@pytest.fixture(scope='session')
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

    def _generate_structure(symbols=None):
        from aiida.plugins import DataFactory

        structure = DataFactory('structure')()

        valid_symbols = [value['symbol'] for value in elements.values()]

        if symbols is not None:
            for symbol in symbols:
                if symbol not in valid_symbols:
                    raise ValueError(f'symbol `{symbol}` is not a valid element.')

                structure.append_atom(position=(0., 0., 0.), symbols=[symbol])

        return structure

    return _generate_structure


@pytest.fixture
def generate_code(aiida_localhost):
    """Generate a `Code` node."""

    def _generate_code(entry_point):
        import random
        import string
        from aiida.plugins import DataFactory

        label = ''.join(random.choice(string.ascii_letters) for _ in range(16))
        code = DataFactory('code')(
            label=label, input_plugin_name=entry_point, remote_computer_exec=[aiida_localhost, '/bin/bash']
        )
        return code

    return _generate_code


@pytest.fixture
def generate_eos_node(generate_structure):
    """Generate an instance of ``EquationOfStateWorkChain``."""

    def _generate_eos_node(include_magnetization=True, include_energy=True):
        from aiida.common import LinkType
        from aiida.orm import Float, WorkflowNode

        node = WorkflowNode(process_type='aiida.workflows:common_workflows.eos').store()

        for index in range(5):
            structure = generate_structure().store()
            structure.add_incoming(node, link_type=LinkType.RETURN, link_label=f'structures__{index}')

            if include_energy:
                energy = Float(index).store()
                energy.add_incoming(node, link_type=LinkType.RETURN, link_label=f'total_energies__{index}')

            if include_magnetization:
                magnetization = Float(index).store()
                magnetization.add_incoming(node, link_type=LinkType.RETURN, link_label=f'total_magnetizations__{index}')

        node.set_exit_status(0)

        return node

    return _generate_eos_node


@pytest.fixture
def generate_dissociation_curve_node():
    """Generate an instance of ``DissociationCurveWorkChain``."""

    def _generate_dissociation_curve_node(include_magnetization=True, include_energy=True):
        from aiida.common import LinkType
        from aiida.orm import Float, WorkflowNode

        node = WorkflowNode(process_type='aiida.workflows:common_workflows.dissociation_curve').store()

        for index in range(5):
            distance = Float(index / 10).store()
            distance.add_incoming(node, link_type=LinkType.RETURN, link_label=f'distances__{index}')

            # `include_energy` can be set to False to test cases with missing outputs
            if include_energy:
                energy = Float(index).store()
                energy.add_incoming(node, link_type=LinkType.RETURN, link_label=f'total_energies__{index}')

            if include_magnetization:
                magnetization = Float(index).store()
                magnetization.add_incoming(node, link_type=LinkType.RETURN, link_label=f'total_magnetizations__{index}')

        node.set_exit_status(0)

        return node

    return _generate_dissociation_curve_node


@pytest.fixture(scope='session')
def generate_upf_data(tmp_path_factory):
    """Return a `UpfData` instance for the given element a file for which should exist in `tests/fixtures/pseudos`."""

    def _generate_upf_data(element):
        """Return `UpfData` node."""
        from aiida_pseudo.data.pseudo import UpfData

        with open(tmp_path_factory.mktemp('pseudos') / f'{element}.upf', 'w+b') as handle:
            content = f'<UPF version="2.0.1"><PP_HEADER\nelement="{element}"\nz_valence="4.0"\n/></UPF>\n'
            handle.write(content.encode('utf-8'))
            handle.flush()
            return UpfData(file=handle)

    return _generate_upf_data


@pytest.fixture(scope='session')
@pytest.mark.usefixtures('with_database')
def sssp(generate_upf_data):
    """Create an SSSP pseudo potential family from scratch."""
    from aiida.plugins import GroupFactory

    SsspFamily = GroupFactory('pseudo.family.sssp')  # pylint: disable=invalid-name

    cutoffs_dict = {'normal': {}}

    with tempfile.TemporaryDirectory() as dirpath:
        for values in elements.values():

            element = values['symbol']
            upf = generate_upf_data(element)
            filename = os.path.join(dirpath, f'{element}.upf')

            with open(filename, 'w+b') as handle:
                with upf.open(mode='rb') as source:
                    handle.write(source.read())
                    handle.flush()

            cutoffs_dict['normal'][element] = {'cutoff_wfc': 30., 'cutoff_rho': 240.}

        label = 'SSSP/1.1/PBE/efficiency'
        family = SsspFamily.create_from_folder(dirpath, label)

    for stringency, cutoffs in cutoffs_dict.items():
        family.set_cutoffs(cutoffs, stringency, unit='Ry')

    return family
