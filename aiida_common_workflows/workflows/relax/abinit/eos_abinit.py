#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Launch script for the common relax work chain demonstrator using Abinit."""
from aiida import load_profile
from aiida.engine import run
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.relax.generator import RelaxType
from common import rescale, structure_init

load_profile()

RelaxWorkChain = WorkflowFactory('common_workflows.relax.abinit')

CALC_ENGINES = {
    'relax': {
        'code': 'abinit-9.2.1-ab@localhost',
        'options': {
            'withmpi': True,
            'max_wallclock_seconds': 86400,
            'resources': {
                'num_machines': 1,
                'num_mpiprocs_per_machine': 2
            }
        }
    }
}


def launch():
    """Launch the relax work chain for a basic silicon crystal structure at a range of scaling factors."""
    relax_type = RelaxType.ATOMS
    protocol = 'moderate'

    structure = structure_init()

    for scale in [0.94, 0.96, 0.98, 1, 1.02, 1.04, 1.06]:
        scaled = rescale(structure, scale)
        generator = RelaxWorkChain.get_inputs_generator()
        #import pdb; pdb.set_trace()
        builder = generator.get_builder(scaled, CALC_ENGINES, protocol, relax_type, threshold_forces=0.001)
        results = run(builder)
        print(results['relaxed_structure'].get_cell_volume(), results['total_energy'].value)


if __name__ == '__main__':
    launch()
