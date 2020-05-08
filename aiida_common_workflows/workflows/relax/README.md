# Relaxation WorkChain common interface

This folder collects the first working example of a common interface among dirrerent plugins for the submission of a task.
This task is the relaxation of a structure.

The file `submission_templete.py` is a file that a hypotetical user should launch in order to complete the task of running the relaxation of a structure. The submission structure is code agnosting, demostarting the achivement of a common interface.
This file also set the standards that the plugin developers should meet when they fulfill their implementation. This includes the standard inputs and outputs we agreed on, the units of measure of the quantities involved and the methods required for the automatic generation of a GUI in the future.
This last point is facilitated by the class `RelaxInputsGenerator` hosted in `generator.py`. This class is meant to be subclassed by code specific `<Code>RelaxInputsGenerator` and provides the implementation of the required methods. The plugin developers only have to define the attributs covering the options supported by their code.
Finally, the WorkChian `CommonRelaxWorkChain` hosted in `workchain.py` constitute the skeleton every code-specific `<Code>RelaxWorkChain` should be based on. It sets the required oututs.

The implementation of each plugin will also be histed here, in a separate folder.
