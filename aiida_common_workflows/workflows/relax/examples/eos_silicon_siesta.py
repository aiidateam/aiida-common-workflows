#!/usr/bin/env runaiida
# -*- coding: utf-8 -*-
"""Launch script for the common relax work chain demonstrator using Siesta."""
from aiida import orm
from aiida.engine import run
from aiida.plugins import DataFactory

from aiida_common_workflows.workflows.relax.generator import RelaxType
from aiida_common_workflows.workflows.relax.siesta import SiestaRelaxInputsGenerator

StructureData = DataFactory('structure')

GENERATOR = SiestaRelaxInputsGenerator
CALC_ENGINES = {
    'relaxation': {
        'code': 'siesta-v4.1-rc1-siesta-bis@localhost',
        'options': {
            'resources': {
                'num_machines': 1
            },
            'max_wallclock_seconds': 86400,
        }
    },
}

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

    filepath = os.path.realpath(os.path.join(os.path.dirname(__file__), 'data/Si.cif'))
    structure = pymatgen.Structure.from_file(filepath, primitive=False)

    return StructureData(pymatgen_structure=structure)


def launch():
    """Launch the relax work chain for a basic silicon crystal structure at a range of scaling factors."""
    relaxation_type = RelaxType.ATOMS
    protocol = 'moderate'

    structure = structure_init()

    for scale in [0.94, 0.96, 0.98, 1, 1.02, 1.04, 1.06]:
        scaled = rescale(structure, scale)
        builder = GENERATOR().get_builder(scaled, CALC_ENGINES, protocol, relaxation_type, threshold_forces=0.001)
        results = run(builder)
        print(results['relaxed_structure'].get_cell_volume(), results['total_energy'].value)


if __name__ == '__main__':
    launch()
