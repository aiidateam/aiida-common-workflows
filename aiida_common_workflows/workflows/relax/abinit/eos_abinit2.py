#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Launch script for the common relax work chain demonstrator using Abinit."""
from aiida import load_profile
from aiida.engine import run
from aiida import orm
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.workflows.eos import EquationOfStateWorkChain

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
                'num_mpiprocs_per_machine': 1
            }
        }
    }
}


def launch():
    """Launch the relax work chain for a basic silicon crystal structure at a range of scaling factors."""
    relaxation_type = RelaxType.ATOMS
    protocol = 'moderate'

    structure = structure_init()

#    scale_factors = orm.List(list = [0.94, 0.96, 0.98, 1, 1.02, 1.04, 1.06])

    generator_inputs = {}
    generator_inputs['calc_engines'] = CALC_ENGINES
    generator_inputs['protocol'] = protocol
    generator_inputs['relaxation_type'] = relaxation_type
    generator_inputs['threshold_forces'] = 0.001
    #generator_inputs['threshold_stress'] = 0.001

    parameters = {}
    parameters['structure'] = structure
#    parameters['scale_factors'] = scale_factors
    parameters['generator_inputs'] = generator_inputs
    parameters['sub_process_class'] = 'common_workflows.relax.abinit'

    run(EquationOfStateWorkChain, **parameters)

        #print(results['relaxed_structure'].get_cell_volume(), results['total_energy'].value)


if __name__ == '__main__':
    launch()
