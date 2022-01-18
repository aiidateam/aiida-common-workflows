# -*- coding: utf-8 -*-
"""
Example to showcase the use of overrides
"""

import pathlib
import ase.io
from aiida.engine import submit
from aiida.plugins import WorkflowFactory
from aiida.orm import KpointsData, StructureData, Dict
import aiida_common_workflows.examples.functions_overrides as fo

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

arg1 = {'port': 'metadata', 'key': 'label', 'value': 'my_label'}

arg2 = {'port': 'parameters', 'key': 'spin', 'value': 'polarized'}

arg3 = {'port': 'kpoints', 'new_node': kp}

a.overrides = {
    'functions': [fo.add_or_replace_dict_item, fo.add_or_replace_dict_item, fo.replace_node],
    'params': [arg1, arg2, arg3]
}

ww = submit(a)
print(ww)
