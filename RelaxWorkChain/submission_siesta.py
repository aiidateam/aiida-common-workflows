"""
File for the submission of a SiestaRelaxWorkChain using default
inputs generated through the method get_builder of the class
SiestaRelaxationInputsGenerator
"""

from aiida.orm import StructureData, Dict, Float, ArrayData
import time
from aiida.engine import submit
from aiida_siesta.workflows.common import SiestaRelaxationInputsGenerator as SiestaRelGen

#This dictionary is the place where the user specifies the code and resources
#to use in order to run the SiestaRelaxWorkChain. 'relax' and 'final_scf' are two steps
#the SiestaRelaxWorkChain that might require two different codes.
job_engines = {
    'relax': {
        'code': 'siesta-4.1@localhost', 
        'options': {
            'resources': {'num_machines': 2}, 
            'max_walltime': 86400, 'queue': 'debug', 'account': 'ABC'
        }
    },
    'final_scf': {
        'code': 'siesta-4.1@localhost', 
        'options': {
            'resources': {'num_machines': 2}, 
            'max_walltime': 3600, 'queue': 'debug', 'account': 'ABC'
        }
    }
}

#The class SiestaRelaxationInputsGenerator is aware of the steps 
#of the SiestaRelaxWorkChain, therefore it can get programmatically the valid step types
assert set(SiestaRelGen.get_step_types()) == set(['relax', 'final_scf'])

#Also  it can return programmatically the schema of each step type (the plugin for the code, that can be used e.g. to show a dropdown list in a GUI of all existing valid codes, and a human-readable decription of what the step does)
assert SiestaRelGen.get_step_type_schema('relax')) == {
    'code_plugin': 'siesta.siesta',
    'description': 'This is the main run of the code, computing the relaxation'}
assert SiestaRelGen.get_step_type_schema('final_scf')) == {
    'code_plugin': 'siesta.siesta',
    'description': 'This is the final SCF that is always performed after a successful relaxation. This typically takes one order of magnitude less CPU time than the relax step'}


#The user choses the protocol (level of accuracy if you want) 
protocol="testing"

#The list of protocols available are listed by get_protocol_names
assert set(SiestaRelGen.get_protocol_names()) == set(['standard', 'testing'])
#there is a default
assert set(SiestaRelGen.get_default_protocol_name()) == 'standard'
#and infos of each protocol can be returned
assert set(SiestaRelGen.get_protocol_info('standard')) == {'description': 'This is the default protocol. This uses a k-mesh with inverse linear density of 0.2 ang^-1 and basis set DZ and pseudos from the "stringent" family from PseudoDojo. This is safe for a default calculation.'}
assert set(SiestaRelGen.get_protocol_info('testing')) == {'description': 'This is a fast protocol to quickly get some results, typically unconverged. This uses a k-mesh with inverse linear density of 0.4 ang^-1 and basis set SZ and pseudos from the "standard" family from PseudoDojo. This is useful for debugging and tutorials.'}


#Other inputs the user need to define:
structure StructureData(...)
relaxation_type = 'variable-cell' # possible values: 'atoms-only', 'variable-cell' (Question: also cell-only? then change the name of variable-cell to full-relax or similar?)


#And some optional inputs
threshold_forces = 0.01 # Optional, units are XXX (defined by our specs). Otherwise, set by default by the protocol.
threshold_stress = 0.1 # Optional, units are XXX (defined by our specs). Otherwise, set by default by the protocol.

#Instance of the class
rel_workflow_gen = SiestaRelGen()


# Get a builder for SiestaRelaxWorkChain, pre-filled, with unstored nodes (unless they are taken from the DB, e.g. pseudos)
builder = rel_workflow_gen.get_builder(structure, job_engines, protocol, relaxation_type, threshold_stress, threshold_forces)


#The user now received a builder with suggested inputs, but before submition he/she has compleate
#freedom to change them. The changes are code-specific and optional, if missing 
#the submission should still work and produce sensible results
new_params = builder.parameters.get_dict() # Assuming that parameters are in the expose_inputs of the WorkChain to run
new_params['max_scf_iterations'] = 200
builder.parameters = Dict(dict=new_params)

# Here we just submit the builder
process_node = submit(builder)

# here: loop to wait for process_node to complete
while process_node.is_running():
    time.sleep(10)

#Standardised output:
assert isinstance(process_node.relaxed_structure, StructureData) # The relaxed structure
assert isinstance(process_node.forces, ArrayData) # These are the forces in XXX units
N = len(process_node.structure.sites)
assert process_node.forces.get_array('forces').shape == (N,3)
assert isinstance(process_node.stress, ArrayData) # This is the stress in XXX units; not present if relaxing atoms only
assert process_node.stress.get_array('stress').shape == (3,3)


#Optional: the total energy in XXX units
assert isinstance(process_node.total_energy, Float)
