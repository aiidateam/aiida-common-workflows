# -*- coding: utf-8 -*-
"""
Here we run the fleur_scf_wc for Si or some other material
"""

import argparse
from pprint import pprint

from aiida.plugins import DataFactory
from aiida.orm import load_node
from aiida.engine import submit, run

from aiida_fleur.tools.common_fleur_wf import is_code, test_and_get_codenode
#from aiida_fleur.workflows.relax import FleurRelaxWorkChain
from aiida_common_workflows.workflows.relax.generator import RelaxType
from aiida_common_workflows.workflows.relax.fleur.generator import FleurRelaxInputsGenerator as InpGen
from aiida_common_workflows.workflows.relax.fleur.workchain import FleurRelaxationWorkChain as RelWC



Dict = DataFactory('dict')
FleurinpData = DataFactory('fleur.fleurinp')
StructureData = DataFactory('structure')

parser = argparse.ArgumentParser(description=('Relax with FLEUR. workflow to optimize '
                                              'the structure. All arguments are pks, or uuids, '
                                              'codes can be names'))
parser.add_argument('--wf_para', type=int, dest='wf_parameters',
                    help='Some workflow parameters', required=False)
parser.add_argument('--structure', type=int, dest='structure',
                    help='The crystal structure node', required=False)
parser.add_argument('--calc_para', type=int, dest='calc_parameters',
                    help='Parameters for the FLEUR calculation', required=False)
parser.add_argument('--inpgen', type=int, dest='inpgen',
                    help='The inpgen code node to use', required=False)
parser.add_argument('--fleur', type=int, dest='fleur',
                    help='The FLEUR code node to use', required=True)
parser.add_argument('--submit', type=bool, dest='submit',
                    help='should the workflow be submited or run', required=False)
parser.add_argument('--options', type=int, dest='options',
                    help='options of the workflow', required=False)
args = parser.parse_args()

print(args)

### Defaults ###
wf_para = Dict(dict={
    'relax_iter': 2,
    'film_distance_relaxation': False,
    'force_criterion': 0.02
})

bohr_a_0 = 0.52917721092 # A
a = 3.486
cell = [[a, 0, 0],
        [0, a, 0],
        [0, 0, a]]
structure = StructureData(cell=cell)
structure.append_atom(position=(0., 0., 0.), symbols='Fe')
structure.append_atom(position=(0.5*a, 0.495*a, 0.0*a), symbols='Fe')
structure.append_atom(position=(0.5*a, 0.0*a, 0.5*a), symbols='Fe')
structure.append_atom(position=(0.01*a, 0.5*a, 0.5*a), symbols='Fe')

parameters = Dict(dict={
    'comp': {
        'kmax': 3.4,
        },
    'atom' : {
        'element' : 'Fe',
        'bmu' : 2.5,
        'rmt' : 2.15
        },
    'kpt': {
        'div1': 4,
        'div2' : 4,
        'div3' : 4
        }})

wf_para_scf = {'fleur_runmax': 2,
               'itmax_per_run': 120,
               'force_converged': 0.002,
               'force_dict': {'qfix': 2,
                              'forcealpha': 0.75,
                              'forcemix': 'straight'},
               'use_relax_xml': True,
               'serial': False,
               'mode': 'force',
               }

wf_para_scf = Dict(dict=wf_para_scf)

options_scf = Dict(dict={'resources': {"num_machines": 1, "num_mpiprocs_per_machine": 1},
                         'queue_name': '',
                         'custom_scheduler_commands': '',
                         'max_wallclock_seconds':  60*60})


fleur_code = is_code(args.fleur)
fleur_inp = test_and_get_codenode(fleur_code, expected_code_type='fleur.fleur')

inpgen_code = is_code(args.inpgen)
inpgen_inp = test_and_get_codenode(inpgen_code, expected_code_type='fleur.inpgen')

inputs = {'scf': {'wf_parameters': wf_para_scf,
                  'structure': structure,
                  'calc_parameters': parameters,
                  'options': options_scf,
                  'inpgen': inpgen_inp,
                  'fleur': fleur_inp
                  },
          'wf_parameters': wf_para
          }


submit_wc = False
if args.submit is not None:
    submit_wc = submit
pprint(inputs)


#### common workchain input
calc_engines = {
    'relax': {
        'code': fleur_inp, #'fleur@local_iff',
        'inputgen' : inpgen_inp, #'inpgen@local_iff',
        'options': {
            'resources': {
                'num_machines': 1,
                "num_mpiprocs_per_machine": 1
            },
            'max_walltime': 86400,
            #'queue': 'debug',
            #'account': 'ABC'
        }
    },
    'final_scf': {
        'code': 'fleur@localhost',
        'inputgen': 'inpgen@local_iff',
        'options': {
            'resources': {
                'num_machines': 1,
                "num_mpiprocs_per_machine": 1
            },
            'max_walltime': 3600,
            #'queue': 'debug',
            #'account': 'ABC'
        }
    }
}



#The user can choose a protocol (a string describing the level of accuracy if you want)
protocol = 'standard' #'testing'
relaxation_type = RelaxType.ATOMS #'atoms'
threshold_stress = None  # Optional, units are ev/ang^3 (defined by our specs). Otherwise, set by default by protocol.
threshold_forces = 0.01  # Optional, units are ev/ang (defined by our specs). Otherwise, set by default by protocol.

# We now create an instance of the class
rel_inp_gen = InpGen()


builder = rel_inp_gen.get_builder(
    structure=structure,
    calc_engines=calc_engines,
    protocol=protocol,
    relaxation_type=relaxation_type,
    threshold_forces=threshold_forces,
    threshold_stress=threshold_stress,
    inpgen = inpgen_inp,
    calc_parameters = parameters
)

print("##################### TEST common_workflow_relax #####################")
# Here we just submit the builder
#process_node = submit(builder)
process_node = run(builder)
# here: in some way we wait for the process to complete execution
#while not process_node.is_terminated:
#    time.sleep(10)

# Here is the standardised output that the WorkChain should produce:
assert isinstance(process_node.relaxed_structure, StructureData)  # The relaxed structure
N = len(process_node.structure.sites)  # Number of atoms, used later

#print("##################### TEST fleur_relax_wc #####################")

#if submit_wc:
#    res = submit(FleurRelaxWorkChain, **inputs)
#    print("##################### Submited fleur_relax_wc #####################")
#    print(("Runtime info: {}".format(res)))
#    print((res.pk))
#    print("##################### Finished submiting fleur_relax_wc #####################")
#
#else:
#    print("##################### Running fleur_relax_wc #####################")
#    res = run(FleurRelaxWorkChain, **inputs)
#    print("##################### Finished running fleur_relax_wc #####################")
