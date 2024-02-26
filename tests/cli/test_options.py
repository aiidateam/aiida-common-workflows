"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import json
import pathlib

import click
import pytest
from aiida import orm
from aiida_common_workflows.cli import options


@pytest.fixture
def filepath_cif():
    """Return a path to a valid CIF file."""
    basepath = pathlib.Path(__file__).parent.parent.parent
    filepath = basepath.joinpath('src', 'aiida_common_workflows', 'common', 'data', 'Si.cif')
    return filepath


@pytest.fixture
def structure_param_type():
    """Return instance of ``StructureDataParamType``."""
    return options.StructureDataParamType()


@pytest.fixture
def json_param_type():
    """Return instance of ``JsonParamType``."""
    return options.JsonParamType()


class TestStructureDataParamType:
    """Test the ``StructureDataParamType``."""

    def test_from_identifier(self, structure_param_type, generate_structure):
        """Test loading from node identifier."""
        structure = generate_structure().store()

        for identifier in [structure.pk, structure.uuid]:
            result = structure_param_type.convert(str(identifier), None, None)
            assert isinstance(result, orm.StructureData)
            assert result.uuid == structure.uuid

    def test_invalid_filepath(self, structure_param_type):
        """Test validation of invalid filepath."""
        with pytest.raises(click.BadParameter, match=r'failed to load .* and it can also not be resolved as a file.'):
            structure_param_type.convert('non-existing.dat', None, None)

    def test_parsing_fails(self, structure_param_type):
        """Test case where parsing of existing file fails."""
        with pytest.raises(click.BadParameter, match=r'file `.*` could not be parsed into a `StructureData`: .*'):
            structure_param_type.convert(pathlib.Path(__file__), None, None)

    def test_parse_from_file(self, structure_param_type, filepath_cif):
        """Test successful parsing from file."""
        result = structure_param_type.convert(filepath_cif, None, None)
        assert isinstance(result, orm.StructureData)
        assert len(result.sites) == 2
        assert result.get_symbols_set() == {'Si'}

    def test_parse_from_file_duplicate(self, structure_param_type, filepath_cif):
        """Test successful parsing from file where node already exists in the database."""
        result = structure_param_type.convert(filepath_cif, None, None)
        structure = result.store()

        result = structure_param_type.convert(filepath_cif, None, None)
        assert result.uuid == structure.uuid

    @pytest.mark.parametrize(
        'label, formula',
        (
            ('Al', 'Al4'),
            ('Fe', 'Fe2'),
            ('GeTe', 'GeTe'),
            ('Si', 'Si2'),
            ('NH3-pyramidal', 'H3N'),
            ('NH3-planar', 'H3N'),
        ),
    )
    def test_parse_predefined_defaults(self, structure_param_type, label, formula):
        """Test the shortcut labels.

        The parameter type should preferentially treat the value as one of the default structure labels. If found it
        should load structure from the corresponding CIF file that is shipped with the repo.
        """
        result = structure_param_type.convert(label, None, None)
        assert result.get_formula() == formula


class TestJsonParamType:
    """Test the ``JsonParamType``."""

    @pytest.mark.parametrize('data', ({'a': 'b', 'c': True, 'd': 134}, 1, 'a', [1, True, '124aa']))
    def test_valid_json_data(self, json_param_type, data):
        """Test loading from a valid JSON string (both dicts and non-dicts)."""
        result = json_param_type.convert(json.dumps(data), None, None)
        assert result == data

    def test_parsing_fails(self, json_param_type):
        """Test case where parsing of a non-valid JSON string fails."""
        with pytest.raises(click.BadParameter, match=r'.*not a valid json.*'):
            json_param_type.convert('inV alidJSON', None, None)


def test_reference_workchain(run_cli_command):
    """Test the ``options.REFERENCE_WORKCHAIN`` option."""
    node = orm.WorkflowNode().store()

    @click.command()
    @options.REFERENCE_WORKCHAIN()
    def command(reference_workchain):
        assert reference_workchain.pk == node.pk

    run_cli_command(command, ['--reference-workchain', str(node.pk)])
