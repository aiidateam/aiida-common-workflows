"""Tests for the :mod:`aiida_common_workflows.cli.utils` module."""
import pytest
from aiida_common_workflows.cli.utils import get_code_from_list_or_database


@pytest.mark.usefixtures('with_clean_database')
def test_get_code_from_list_or_database(generate_code):
    """Test `get_code_from_list_or_database` method."""
    entry_point = 'quantumespresso.pw'

    # No explicit codes nor stored in the database
    assert get_code_from_list_or_database([], entry_point) is None

    codes = [generate_code(entry_point).store(), generate_code(entry_point).store()]

    # From explicit code list
    assert get_code_from_list_or_database(codes, entry_point).uuid == codes[0].uuid

    # Empty list, but database contains a code. Note that order is random here, so we don't know which code is returned.
    assert get_code_from_list_or_database([], entry_point).uuid in [code.uuid for code in codes]
