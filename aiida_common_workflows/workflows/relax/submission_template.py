# -*- coding: utf-8 -*-
"""
Reference file showcasing how the submission of a `<Code>RelaxWorkChain` would work, when using
inputs generated through the method `get_builder` of a class `<Code>RelaxInputGenerator`.
Moreover this example shows the required outputs of `<Code>RelaxWorkChain`, including the units specifications.
"""

from aiida.orm import StructureData, Dict, Float, ArrayData
import time
from aiida.engine import submit
from aiida_common_workflows.workflows.relax.<code>.generator import <Code>RelaxInputGenerator as InpGen
from aiida_common_workflows.workflows.relax.<code>.workchain import <Code>RelaxWorkChain as RelWC

# This dictionary is the place where the user specifies the code and (optionally) resources
# to use in order to run the RelWC. 'relax' and 'final_scf' are two steps
# that the RelWC might have, and that might require two different codes.
# More generally: we expect the WorkChain to eventually run (one or more) CalcJob(s).
# These might require specific options, and need to know which code to use.
# Therefore, the generator should group all possible runs of CalcJobs in groups that share the same code
# and the same resources. We call them `calc_types`. The same code might be used by multiple calc_types (see
# e.g. example below) if the resources needed are very different.
# Multiple calculations might use the same calc_type, e.g. restarts in the same part of the WorkChain.
# The keys of the following engines are the allowed calc_types; the values define the
# concrete values for each of these calc_types.
#The schema of engines is code dependent, therefore there is a method to explore it,
#see next call
engines = {
    'relax': {
        'code': '<code>@localhost',
        'options': {
            'resources': {
                'num_machines': 2
            },
            'max_walltime': 86400,
            'queue': 'debug',
            'account': 'ABC'
        }
    },
    'final_scf': {
        'code': '<code>@localhost',
        'options': {
            'resources': {
                'num_machines': 2
            },
            'max_walltime': 3600,
            'queue': 'debug',
            'account': 'ABC'
        }
    }
}

# The class InpGen must be aware of the calc_types
# of the RelWC, therefore it can get programmatically all valid calc_types
# through the method get_calc_types()
assert set(InpGen.get_calc_types()) == set(['relax', 'final_scf'])

# Also, it returns programmatically the schema of each calc_type (including the plugin for the code,
# that can be used e.g. to show a dropdown list in a GUI of all existing valid codes;
# and a human-readable decription of what the calc_type does)
assert InpGen.get_calc_type_schema('relax') == {
    'code_plugin': 'siesta.siesta',
    'description': 'These are calculations used for the main run of the code, computing the relaxation'
}
assert InpGen.get_calc_type_schema('final_scf') == {
    'code_plugin': 'siesta.siesta',
    'description':
    'This is the final SCF calculation that is always performed after a successful relaxation. '
    'This typically takes one order of magnitude less CPU time than the relax step'
}

#The user can choose a protocol (a string describing the level of accuracy if you want)
protocol = 'moderate'

# The list of protocols available are listed by get_protocol_names
assert set(InpGen.get_protocol_names()) == set(['fast', 'moderate', 'precise'])
# There is a default and we can ask for it
assert set(InpGen.get_default_protocol_name()) == 'standard'
# Also in this case, we can ask for information on each protocol (again useful for GUIs for instance)
assert set(InpGen.get_protocol('moderate')) == {
    'description':
    'This is the default protocol. This uses a k-mesh with inverse linear density of '
    '0.2 ang^-1 and basis set ... and pseudos from .... This is safe for a default calculation.'
}

# Another compulsory input, specifying the task. Typical values: 'atoms', 'cell'
# but every plugin is free to implement its own
relax_type = 'atoms'

# As some codes might support limited functionality (for instance fleur can't relax the cell),
# it is useful to have a method returning the available `relax_type`
assert set(InpGen.get_relax_types()) == set(['atoms', 'cell', 'atoms_cell'])

#Other inputs the user need to define:
structure = StructureData()  # The initial structure is a compulsory input
## Anything to properly define the StructureData here

# And some optional inputs
threshold_forces = 0.01  # Optional, units are ev/ang (defined by our specs). Otherwise, set by default by protocol.
threshold_stress = 0.1  # Optional, units are ev/ang^3 (defined by our specs). Otherwise, set by default by protocol.

# We now create an instance of the class
rel_inp_gen = InpGen()

# This is the main call: we get a builder for a `RelWC`, pre-filled,
# with unstored nodes (unless they are taken from the DB, e.g. pseudos)
builder = rel_inp_gen.get_builder(
    structure=structure,
    engines=engines,
    protocol=protocol,
    relax_type=relax_type,
    threshold_forces=threshold_forces,
    threshold_stress=threshold_stress
)
#Some extra, code-specific, inputs mught be implemented as required inputs of `get_builder`

# The user now received a builder with suggested inputs, but before submission he/she has complete
# freedom to change any of them.
# NOTE: The changes are code-specific and optional.
# If no change is performed, just submitting the builder should still work and produce sensible results.
new_params = builder.parameters.get_dict()  # Assuming that `parameters` is an input of the RelWC to run
new_params['max_scf_iterations'] = 200
builder.parameters = Dict(dict=new_params)

# Here we just submit the builder
process_node = submit(builder)

# here: in some way we wait for the process to complete execution
while not process_node.is_terminated:
    time.sleep(10)

# Here is the standardised output that the WorkChain should produce:
assert isinstance(process_node.relaxed_structure, StructureData)  # The relaxed structure
N = len(process_node.structure.sites)  # Number of atoms, used later

## FORCES
assert isinstance(process_node.forces, ArrayData)  # These are the forces in eV/ang units
assert process_node.forces.get_array('forces').shape == (N, 3)  # Shape of the 'forces' array (inside the node)

## STRESS (optional, not present if relaxing atoms only)
assert isinstance(process_node.stress, ArrayData)  # This is the stress in ev/ang^3 units
assert process_node.stress.get_array('stress').shape == (3, 3)

#Optional: the total energy in eV units
assert isinstance(process_node.total_energy, Float)
