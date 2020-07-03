# -*- coding: utf-8 -*-
"""
Relax run on Si example for Fleur
"""
import os.path as op
from aiida import orm
from aiida.engine import run_get_node
from aiida_common_workflows.workflows.relax.generator import RelaxType

#Next three lines must be modified.

from aiida_common_workflows.workflows.relax.fleur.generator import FleurRelaxInputsGenerator as InpGenFleur
#from aiida_common_workflows.workflows.relax.fleur.workchain import FleurRelaxWorkChain as RelWC
InpGen = InpGenFleur()
calc_engines = {
    'relax': {
        'code': 'fleur-0.30-fleur_MPI@localhost',
        'inputgen': 'fleur-0.30-inpgen@localhost',
        'options': {
            'resources': {
                'num_machines': 1,
                'num_mpiprocs_per_machine': 1
            },
            'max_walltime': 86400,
        }
    }
}

#Don't touch the rest

relaxation_type = RelaxType.ATOMS
protocol = 'moderate'


def rescale(structure, scale):
    """
    Calcfunction to rescale a structure by a scaling factor.
    Uses ase.
    :param structure: An AiiDA structure to rescale
    :param scale: The scale factor
    :return: The rescaled structure
    """

    the_ase = structure.get_ase()
    new_ase = the_ase.copy()
    new_ase.set_cell(the_ase.get_cell() * float(scale), scale_atoms=True)
    new_structure = orm.StructureData(ase=new_ase)
    print(new_structure.cell)
    print(structure.sites)
    return new_structure


def structure_init():
    """
    Workfunction to create structure of a given element taking it from a reference
    list of scructures and a reference volume.
    :param element: The element to create the structure with.
    :return: The structure and the kpoint mesh (from file, releted to the structure!).
    """
    import pymatgen as mg

    structure_file = op.realpath(op.join(op.dirname(__file__), 'data/Si_51688.cif'))  #Si.cif'))

    in_structure = mg.Structure.from_file(structure_file, primitive=False)

    newreduced = in_structure.copy()
    #newreduced.scale_lattice(float(20.4530) * in_structure.num_sites)
    structure = orm.StructureData(pymatgen_structure=newreduced)

    return structure


structure = structure_init()

for scale in [0.94, 0.96, 0.98, 1, 1.02, 1.04, 1.06]:
    scaled = rescale(structure, scale)
    builder = InpGen.get_builder(scaled, calc_engines, protocol, relaxation_type, threshold_forces=0.001)
    future = run_get_node(builder)
    print(future)
    #print('Launching {0} at volume rescaled of {1}'.format(future[1].pk, scale))
