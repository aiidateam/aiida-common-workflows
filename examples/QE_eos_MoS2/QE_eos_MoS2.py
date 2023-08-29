from aiida import engine, orm
from aiida.plugins import CalculationFactory

from aiida.plugins import WorkflowFactory
from aiida.orm import List, Dict
from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType



code = orm.load_code('qe.pw@local_slurm') 

#load silicon structure
cif = orm.CifData(file="/home/max/Desktop/Aiida_DFTK_Test/common_workflow/aiida-common-workflows/examples/QE_eos_MoS2/MoS2.cif")
structure = cif.get_structure()



RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')  # Load the relax workflow implementation of choice.

structure = structure # A `StructureData` node representing the structure to be optimized.
engines = {
    'relax': {
        'code': code,  # An identifier of a `Code` configured for the `quantumespresso.pw` plugin
        'options': {
            'withmpi': False,
            'resources': {
                'num_machines': 1,  # Number of machines/nodes to use
                'num_mpiprocs_per_machine': 1,
            },
            'max_wallclock_seconds': 3600,  # Number of wallclock seconds to request from the scheduler for each job
        }
    }
}



cls = WorkflowFactory('common_workflows.eos')

inputs = {
    'structure': structure,
    'scale_factors': List(list=[0.90, 0.94, 0.96, 1, 1.04, 1.06, 1.08]),
    'generator_inputs': {  # code-agnostic inputs for the relaxation
        'engines': engines,
        'protocol': 'fast',
        'relax_type': RelaxType.NONE
    },
    'sub_process_class': 'common_workflows.relax.quantum_espresso'
}

engine.run(cls, **inputs)