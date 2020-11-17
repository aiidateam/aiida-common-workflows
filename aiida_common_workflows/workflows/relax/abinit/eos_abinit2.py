#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Launch script for the common relax work chain demonstrator using Abinit."""
from pymatgen import Structure

from aiida import load_profile, orm
from aiida.engine import run
from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain
from aiida_common_workflows.workflows.relax.generator import RelaxType

load_profile()

# CODE = 'abinit-9.2.1-ab@localhost'
CODE = 'abinit_9.2.1'
STRUCTURE = 'Si'  # Si, Al, GeTe, Fe
# For Si
KWARGS = {'magnetism': None, 'initial_magnetization': None, 'is_metallic': False, 'do_soc': False}
# For Al
# KWARGS = {'magnetism': None, 'initial_magnetization': None, 'is_metallic': True, 'tsmear': 0.01, 'do_soc': False}
# Fe Ferro
# KWARGS = {'magnetism': 'ferro', 'initial_magnetization': [[0.0, 0.0, 4.0], [0.0, 0.0, 4.0]],
#           'is_metallic': True, 'tsmear': 0.01, 'do_soc': False}
# Fe Antiferro
# # KWARGS = {'magnetism': 'antiferro', 'initial_magnetization': [[0.0, 0.0, 4.0], [0.0, 0.0, -4.0]],
#             'is_metallic': True, 'tsmear': 0.01, 'do_soc': False}
# For GeTe
# KWARGS = {'magnetism': None, 'initial_magnetization': None, 'is_metallic': False, 'do_soc': True}


def launch():
    """Launch the relax work chain for a basic silicon crystal structure at a range of scaling factors."""

    print(f'Running {STRUCTURE} with {CODE}')

    pymatgen_structure = Structure.from_file(f'../../../common/data/{STRUCTURE}.cif')
    structure = orm.StructureData(pymatgen=pymatgen_structure)

    parameters_dict = {
        'structure': structure,
        'sub_process_class': 'common_workflows.relax.abinit',
        'generator_inputs': {
            'protocol': 'precise',
            'relax_type': RelaxType.ATOMS,
            'threshold_forces': 0.001,
            'calc_engines': {
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
            },
            **KWARGS
        }
    }

    run(EquationOfStateWorkChain, **parameters_dict)


if __name__ == '__main__':
    launch()
