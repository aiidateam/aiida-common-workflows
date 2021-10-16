# -*- coding: utf-8 -*-
"""Module collecting functions to modify StructureData objects."""
from aiida.engine import calcfunction

__all__ = ('seekpath_explicit_kp_path',)


@calcfunction
def seekpath_explicit_kp_path(structure, seekpath_params):
    """
    Return the modified structure of SeekPath and the explicit list of kpoints.
    :param structure: StructureData containing the structure information.
    :param seekpath_params: Dict of seekpath parameters to be unwrapped as arguments of `get_explicit_kpoints_path`.
    """
    from aiida.tools import get_explicit_kpoints_path

    results = get_explicit_kpoints_path(structure, **seekpath_params)

    return {'structure': results['primitive_structure'], 'kpoints': results['explicit_kpoints']}
