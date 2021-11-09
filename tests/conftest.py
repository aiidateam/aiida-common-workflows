# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Configuration and fixtures for unit test suite."""
import os
import io
import tempfile

import click
import pytest

from aiida import engine
from aiida.common import exceptions
from aiida.common.constants import elements

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']  # pylint: disable=invalid-name


@pytest.fixture(scope='session', autouse=True)
def with_database(aiida_profile):
    """Alias for the ``aiida_profile`` fixture from ``aiida-core``."""
    yield aiida_profile


@pytest.fixture
def with_clean_database(with_database):
    """Fixture to clear the database before yielding to the test."""
    with_database.reset_db()
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
def generate_input_generator_cls():
    """Return a factory to create a subclass of an ``InputGenerator``."""

    def _generate_input_generator_cls(inputs_dict=None):
        """Generate a subclass of ``InputGenerator``.

        :param inputs_dict: an optional dictionary of inputs to be defined on the process spec.
        :param namespaces: an optional list of namespaces to be defined on the process spec.
        """
        from aiida_common_workflows.generators import InputGenerator

        class TestInputGenerator(InputGenerator):
            """Test subclass of ``InputGenerator``."""

            _protocols = {'moderate': {'description': 'bla'}}
            _default_protocol = 'moderate'

            @classmethod
            def define(cls, spec):
                super().define(spec)

                if inputs_dict is not None:
                    for k, val in inputs_dict.items():
                        spec.input(k, valid_type=val)

            def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
                builder = self.process_class.get_builder()
                return builder

        return TestInputGenerator

    return _generate_input_generator_cls


@pytest.fixture
def generate_structure():
    """Generate a `StructureData` node."""

    def _generate_structure(symbols=None):
        from aiida.plugins import DataFactory

        structure = DataFactory('structure')()

        valid_symbols = [value['symbol'] for value in elements.values()]

        if symbols is not None:
            for index, symbol in enumerate(symbols):
                if symbol not in valid_symbols:
                    raise ValueError(f'symbol `{symbol}` is not a valid element.')

                structure.append_atom(position=(0. + index * 1, 0. + index * 1, 0. + index * 1), symbols=[symbol])

        return structure

    return _generate_structure


@pytest.fixture
def generate_code(aiida_localhost):
    """Generate a `Code` node."""

    def _generate_code(entry_point):
        import random
        import string
        from aiida.plugins import DataFactory

        aiida_localhost.set_default_mpiprocs_per_machine(1)

        label = ''.join(random.choice(string.ascii_letters) for _ in range(16))
        code = DataFactory('code')(
            label=label, input_plugin_name=entry_point, remote_computer_exec=[aiida_localhost, '/bin/bash']
        )
        return code

    return _generate_code


@pytest.fixture
def generate_workchain():
    """Generate an instance of a ``WorkChain``."""

    def _generate_workchain(entry_point, inputs):
        """Generate an instance of a ``WorkChain`` with the given entry point and inputs.

        :param entry_point: entry point name of the work chain subclass.
        :param inputs: inputs to be passed to process construction.
        :return: a ``WorkChain`` instance.
        """
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import WorkflowFactory

        process_class = WorkflowFactory(entry_point)
        runner = get_manager().get_runner()
        process = instantiate_process(runner, process_class, **inputs)

        return process

    return _generate_workchain


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
def generate_upf_data():
    """Return a `UpfData` instance for the given element."""

    def _generate_upf_data(element):
        """Return `UpfData` node."""
        from aiida_pseudo.data.pseudo import UpfData
        content = f'<UPF version="2.0.1"><PP_HEADER\nelement="{element}"\nz_valence="4.0"\n/></UPF>\n'
        stream = io.BytesIO(content.encode('utf-8'))
        return UpfData(stream, filename=f'{element}.upf')

    return _generate_upf_data


@pytest.fixture(scope='session')
def generate_psml_data():
    """Return a `PsmlData` instance for the given element."""

    def _generate_psml_data(element):
        """Return `PsmlData` node."""
        from textwrap import dedent
        from aiida_pseudo.data.pseudo import PsmlData

        content = dedent(
            f"""<?xml version="1.0" encoding="UTF-8" ?>
            <psml version="1.1" energy_unit="hartree" length_unit="bohr">
            <pseudo-atom-spec atomic-label="{element}" atomic-number="2"></pseudo-atom-spec>
            </psml>
            """
        )
        stream = io.BytesIO(content.encode('utf-8'))
        return PsmlData(stream, filename=f'{element}.psml')

    return _generate_psml_data


@pytest.fixture(scope='session')
def generate_jthxml_data():
    """Return a ``JthXmlData`` instance for the given element."""

    def _generate_jthxml_data(element):
        """Return ``JthXmlData`` node."""
        from textwrap import dedent
        from aiida_pseudo.data.pseudo import JthXmlData

        content = dedent(
            f"""<?xml  version="1.0"?>
            <paw_dataset version="0.7">
            <atom symbol="{element}" Z="2.00" core="0.00" valence="2.00"/>
            </paw_dataset>
            """
        )
        stream = io.BytesIO(content.encode('utf-8'))
        return JthXmlData(stream, filename=f'{element}.jthxml')

    return _generate_jthxml_data


@pytest.fixture(scope='session')
def sssp(generate_upf_data):
    """Create an SSSP pseudo potential family from scratch."""
    from aiida.plugins import GroupFactory

    SsspFamily = GroupFactory('pseudo.family.sssp')  # pylint: disable=invalid-name
    label = 'SSSP/1.1/PBE/efficiency'

    try:
        family = SsspFamily.objects.get(label=label)
    except exceptions.NotExistent:
        pass
    else:
        return family

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

        family = SsspFamily.create_from_folder(dirpath, label)

    for stringency, cutoffs in cutoffs_dict.items():
        family.set_cutoffs(cutoffs, stringency, unit='Ry')

    return family


@pytest.fixture(scope='session')
def pseudo_dojo(generate_jthxml_data):
    """Create a PseudoDojo pseudo potential family from scratch."""
    from aiida import plugins

    PseudoDojoFamily = plugins.GroupFactory('pseudo.family.pseudo_dojo')  # pylint: disable=invalid-name
    label = 'PseudoDojo/1.0/PBE/SR/standard/jthxml'

    try:
        family = PseudoDojoFamily.objects.get(label=label)
    except exceptions.NotExistent:
        pass
    else:
        return family

    cutoffs_dict = {'normal': {}}

    with tempfile.TemporaryDirectory() as dirpath:
        for values in elements.values():

            element = values['symbol']
            upf = generate_jthxml_data(element)
            filename = os.path.join(dirpath, f'{element}.jthxml')

            with open(filename, 'w+b') as handle:
                with upf.open(mode='rb') as source:
                    handle.write(source.read())
                    handle.flush()

            cutoffs_dict['normal'][element] = {'cutoff_wfc': 30., 'cutoff_rho': 240.}

        family = PseudoDojoFamily.create_from_folder(dirpath, label, pseudo_type=plugins.DataFactory('pseudo.jthxml'))

    for stringency, cutoffs in cutoffs_dict.items():
        family.set_cutoffs(cutoffs, stringency, unit='Eh')

    return family


@pytest.fixture(scope='session')
def psml_family(generate_psml_data):
    """Create a pseudopotential family with PsmlData potentials from scratch."""
    from aiida import plugins

    PsmlData = plugins.DataFactory('pseudo.psml')  # pylint: disable=invalid-name
    PseudoPotentialFamily = plugins.GroupFactory('pseudo.family')  # pylint: disable=invalid-name
    label = 'nc-sr-04_pbe_standard_psml'

    try:
        family = PseudoPotentialFamily.objects.get(label=label)
    except exceptions.NotExistent:
        pass
    else:
        return family

    with tempfile.TemporaryDirectory() as dirpath:
        for values in elements.values():

            element = values['symbol']
            upf = generate_psml_data(element)
            filename = os.path.join(dirpath, f'{element}.psml')

            with open(filename, 'w+b') as handle:
                with upf.open(mode='rb') as source:
                    handle.write(source.read())
                    handle.flush()

        family = PseudoPotentialFamily.create_from_folder(dirpath, label, pseudo_type=PsmlData)

    return family
