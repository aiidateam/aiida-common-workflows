# -*- coding: utf-8 -*-
import os.path as op
from aiida import orm
from aiida.engine import run
from aiida_common_workflows.workflows.relax.generator import RelaxType

#Next three lines must be modified.

#from aiida_common_workflows.workflows.relax. #... import MyInpGen
#InpGen = #MyInpGen
#calc_engines = #my cal eng schema
#{
#    'relax': {
#        'code': '<code>@localhost',
#        'options': {
#            'resources': {
#                'num_machines': 2
#            },
#            'max_walltime': 86400,
#        }
#    },
#    'maybe another step?': {
#        'code': '<code>@localhost',
#        'options': {
#            'resources': {
#                'num_machines': 2
#            },
#            'max_walltime': 3600,
#            'queue': 'debug',
#            'account': 'ABC'
#        }
#    }
#}

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

    return new_structure

def structure_init():
    """
    Workfunction to create structure of a given element taking it from a reference
    list of scructures and a reference volume.
    :param element: The element to create the structure with.
    :return: The structure and the kpoint mesh (from file, releted to the structure!).
    """
    import pymatgen as mg

    structure_file = op.realpath(op.join(op.dirname(__file__), 'data/Si.cif'))

    in_structure = mg.Structure.from_file(structure_file, primitive=False)

    newreduced = in_structure.copy()
    newreduced.scale_lattice(float(20.4530) * in_structure.num_sites)
    structure = orm.StructureData(pymatgen_structure=newreduced)

    return structure

structure = structure_init()

for scale in [0.94,0.96,0.98,1,1.02,1.04,1.06]:
    scaled = rescale(structure, scale)
    builder = InpGen.get_builder(scaled, calc_engines, protocol, relaxation_type, threshold_forces=0.001)
    future = run(builder)
    print('Launching {0} at volume rescaled of {1}'.format(future.pk, scale))
