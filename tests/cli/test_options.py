# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,no-self-use
"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import pathlib

import click
import pytest

from aiida import orm
from aiida_common_workflows.cli import options


@pytest.fixture
def filepath_cif():
    """Return a path to a valid CIF file."""
    basepath = pathlib.Path(__file__).parent.parent.parent
    filepath = basepath.joinpath('aiida_common_workflows', 'common', 'data', 'Si.cif')
    return filepath


@pytest.fixture
def param_type():
    """Return instance of ``StructureDataParamType``."""
    return options.StructureDataParamType()


class TestStructureDataParamType:
    """Test the ``StructureDataParamType``."""

    def test_from_identifier(self, param_type, generate_structure):
        """Test loading from node identifier."""
        structure = generate_structure().store()

        for identifier in [structure.pk, structure.uuid]:
            result = param_type.convert(str(identifier), None, None)
            assert isinstance(result, orm.StructureData)
            assert result.uuid == structure.uuid

    def test_invalid_filepath(self, param_type):
        """Test validation of invalid filepath."""
        with pytest.raises(click.BadParameter, match=r'failed to load .* and it can also not be resolved as a file.'):
            param_type.convert('non-existing.dat', None, None)

    def test_parsing_fails(self, param_type):
        """Test case where parsing of existing file fails."""
        with pytest.raises(click.BadParameter, match=r'file `.*` could not be parsed into a `StructureData`: .*'):
            param_type.convert(pathlib.Path(__file__), None, None)

    def test_parse_from_file(self, param_type, filepath_cif):
        """Test successful parsing from file."""
        result = param_type.convert(filepath_cif, None, None)
        assert isinstance(result, orm.StructureData)
        assert len(result.sites) == 2
        assert result.get_symbols_set() == {'Si'}

    def test_parse_from_file_duplicate(self, param_type, filepath_cif):
        """Test successful parsing from file where node already exists in the database."""
        result = param_type.convert(filepath_cif, None, None)
        structure = result.store()

        result = param_type.convert(filepath_cif, None, None)
        assert result.uuid == structure.uuid

    @pytest.mark.parametrize(
        'label, formula', (
            ('Al', 'Al4'),
            ('Fe', 'Fe2'),
            ('GeTe', 'GeTe'),
            ('Si', 'Si2'),
            ('NH3-pyramidal', 'H3N'),
            ('NH3-planar', 'H3N'),
        )
    )
    def test_parse_predefined_defaults(self, param_type, label, formula):
        """Test the shortcut labels.

        The parameter type should preferentially treat the value as one of the default structure labels. If found it
        should load structure from the corresponding CIF file that is shipped with the repo.
        """
        result = param_type.convert(label, None, None)
        assert result.get_formula() == formula


def test_previous_workchain(run_cli_command):
    """Test the ``options.PREVIOUS_WORKCHAIN`` option."""
    node = orm.WorkflowNode().store()

    @click.command()
    @options.PREVIOUS_WORKCHAIN()
    def command(previous_workchain):
        assert previous_workchain.pk == node.pk

    run_cli_command(command, ['--previous-workchain', str(node.pk)])
