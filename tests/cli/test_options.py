# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,no-self-use
"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import pathlib

import click
import pytest

from aiida import orm
from aiida_common_workflows.cli.options import StructureDataParamType


@pytest.fixture
def filepath_cif():
    """Return a path to a valid CIF file."""
    basepath = pathlib.Path(__file__).parent.parent.parent
    filepath = basepath.joinpath('aiida_common_workflows', 'common', 'data', 'Si.cif')
    return filepath


@pytest.fixture
def param_type():
    """Return instance of ``StructureDataParamType``."""
    return StructureDataParamType()


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
