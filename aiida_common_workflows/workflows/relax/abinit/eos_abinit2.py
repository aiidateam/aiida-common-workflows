#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Launch script for the common relax work chain demonstrator using Abinit."""
from pymatgen import Structure

from aiida import load_profile, orm
from aiida.engine import run
from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain
from aiida_common_workflows.workflows.relax.generator import RelaxType

load_profile()

CODE = 'abinit-9.2.1-ab@localhost'
# CODE = 'abinit_9.2.1'
STRUCTURE = 'Al'  # Si, Al, GeTe, Fe
MAGNETISM = 'no' # Possibilities are 'no', 'ferro' or 'anti'
INITIAL_MAG = 0.0 # Should be a float and is the initial magnetisation. For Fe should be 4.0
SOC = 'no' # Possibilities are 'yes' or 'no'
METAL = 'yes' # If the material is a metal, we need to change the occupation type

def launch():
    """Launch the relax work chain for a basic silicon crystal structure at a range of scaling factors."""

    print(f'Running {STRUCTURE} with {CODE}')

    pymatgen_structure = Structure.from_file(f'../../../common/data/{STRUCTURE}.cif')
    structure = orm.StructureData(pymatgen=pymatgen_structure)

    parameters_dict = {
        'structure': structure,
        'sub_process_class': 'common_workflows.relax.abinit',
        'generator_inputs': {
            'protocol': 'moderate',
            'relaxation_type': RelaxType.ATOMS,
            'threshold_forces': 0.001,
            'calc_engines': {
                'magnetism' : MAGNETISM, 
                'initial_mag' : INITIAL_MAG, 
                'SOC' : SOC, 
                'metal' : METAL,
                'relax': {
                    'code': CODE,
                    'options': {
                        'withmpi': True,
                        'max_wallclock_seconds': 24 * 60**2,
                        'resources': {
                            'num_machines': 1,
                            'num_mpiprocs_per_machine': 4
                        }
                    }
                }
            }
        }
    }

    run(EquationOfStateWorkChain, **parameters_dict)


if __name__ == '__main__':
    launch()
