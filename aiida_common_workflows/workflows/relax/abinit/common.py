# -*- coding: utf-8 -*-
"""Common functions for the demonstration launch scripts of the common relax workflows."""
from aiida import orm
from aiida.plugins import DataFactory

StructureData = DataFactory('structure')

def rescale(structure: StructureData, scale: orm.Float) -> StructureData:
    """Rescale a structure by a scaling factor using ASE.
    :param structure: structure to rescale.
    :param scale: the scale factor.
    :return: rescaled structure.
    """
    ase = structure.get_ase().copy()
    ase.set_cell(ase.get_cell() * float(scale), scale_atoms=True)
    return StructureData(ase=ase)


def structure_init() -> StructureData:
    """Return a silicon structure constructed from the `data/Si.cif` file.
    :return: silicon crystal structure.
    """
    import os
    import pymatgen

    filepath = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../../common/data/Si.cif'))
    structure = pymatgen.Structure.from_file(filepath, primitive=False)

    return StructureData(pymatgen_structure=structure)
