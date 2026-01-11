from aiida import orm
from aiida.engine import run_get_node
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.plugins import get_entry_point_name_from_class, load_workflow_entry_point
from ase.build import bulk

PLUGIN_NAME = 'abacus'
CODE_LABEL = 'abacus@localhost'


structure = orm.StructureData(ase=bulk('Si', 'diamond', 5.4))
print(f'Structure PK: {structure.pk}')

sub_process_cls = load_workflow_entry_point('relax', 'abacus')
sub_process_cls_name = get_entry_point_name_from_class(sub_process_cls).name
generator = sub_process_cls.get_input_generator()

engine_types = generator.spec().inputs['engines']
engines = {}
# There should be only one
for engine in engine_types:
    engines[engine] = {
        'code': CODE_LABEL,
        'options': {
            'resources': {'num_machines': 1, 'tot_num_mpiprocs': 1},
            'max_wallclock_seconds': 1700,  # A bit less than 30 minutes (so we fit in the debug queue=partition)
        },
    }

inputs = {
    'structure': structure,
    'generator_inputs': {  # code-agnostic inputs for the relaxation
        'engines': engines,
        'protocol': 'fast',
        'relax_type': RelaxType.NONE,
        'electronic_type': ElectronicType.METAL,
        'spin_type': SpinType.NONE,
    },
    'sub_process_class': sub_process_cls_name,
    # 'sub_process' : {  # optional code-dependent overrides
    #     'base': {
    #         ## In order to make this work, you have perform the change discussed
    #         ## at the bottom of the file in the eos.py file.
    #         ## Otherwise the whole namespace is replaced.
    #         'abacus': {
    #             'parameters': orm.Dict(dict={
    #                 'input': {
    #                     'cal_stress': True
    #                 }
    #             })
    #         }
    #     }
    # }
}

cls = WorkflowFactory('common_workflows.eos')
results, node = run_get_node(cls, **inputs)
print(f'Submitted workflow with PK = {node.pk} for {structure.get_formula()}')
print(f'Results: {results}')
