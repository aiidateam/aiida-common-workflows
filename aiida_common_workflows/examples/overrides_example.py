# -*- coding: utf-8 -*-
"""
Example to showcase the use of overrides
"""

import pathlib
import ase.io
from aiida.engine import submit
from aiida.plugins import WorkflowFactory
from aiida.orm import KpointsData, StructureData, Dict, List

CODE = 'siesta-school--MaX-1.3.0-1@localhost'

a = WorkflowFactory('common_workflows.relax_code_agnostic').get_builder()

si_ase = ase.io.read(pathlib.Path(__file__).parent / '../' / 'common' / 'data' / 'Si.cif')

engines = {
    'relax': {
        'code': CODE,
        'options': Dict(dict={
            'max_wallclock_seconds': 3600,
            'resources': {
                'num_machines': 1
            }
        })
    }
}

a.relax_sub_process_class = 'common_workflows.relax.siesta'
a.protocol = 'fast'
a.engines = engines
a.structure = StructureData(ase=si_ase)

kp = KpointsData()
kp.set_kpoints_mesh([4, 4, 4])
kp.store()

a.overrides = [
        #{
        #    'entrypoint': 'generic.add_or_replace',
        #    'kwargs': {'port': 'metadata', 'key': 'label', 'value': 'my_label'}
        #},
        {
            'entrypoint': 'generic.add_or_replace_node',
            'kwargs': {'port': 'kpoints', 'new_node': kp}
        },
        #{
        #    'entrypoint': 'relax.smearing.siesta', 
        #    'kwargs': {'port': 'kpoints', 'new_node': kp}
        #},
        #{
        #    'entrypoint': 'relax.siesta.basis',
        #    'kwargs': {'port': 'kpoints', 'new_node': kp}
        #}
]

ww = submit(a)
print(ww)
