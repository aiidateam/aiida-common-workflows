# Relaxation WorkChain common interface

This folder collects the first working example of a common interface among dirrerent plugins for the submission of a task.
This task is the relaxation of a structure.

The file `submission_templete.py` is a file that a hypotetical user should launch in order to complete the task of running the relaxation of a structure. The submission structure is code agnosting, demostarting the achivement of a common interface.
This file also set the standards that the plugin developers should meet when they fulfill their implementation. This includes the standard inputs and outputs we agreed on, the units of measure of the quantities involved and the methods required for the automatic generation of a GUI in the future.
This last point is facilitated by the class `RelaxInputsGenerator` hosted in `generator.py`. This class is meant to be subclassed by code specific `<Code>RelaxInputsGenerator` and provides the implementation of the required methods. The plugin developers only have to define the attributs covering the options supported by their code.
Finally, the WorkChian `CommonRelaxWorkChain` defined in the module `workchain.py` provides a base implementation of a `WorkChain` that will be the wrapper workchain around code-specific workchains to guarantee a homogeneous interface.
Essentially, it functions by transforming the outputs of the code specific workchain to the conventions of the common interface.
The inputs are automatically integrated through the `expose_inputs` functionality of the process specification and the `RelaxInputGenerator` will ensure a homogenous interface for the input determination across plugins.
Each plugin should subclass it with the naming convention `<Code>RelaxWorkChain`, set the correct subclass for the `_process_class` class attribute and implement the `convert_outputs` method.

The implementation of each plugin will also be histed here, in a separate folder.
