# Relaxation WorkChain common interface

This folder collects the first working example of a common interface among dirrerent plugins for the submission of a task.
This task is the relaxation of a structure.

The file `submission_templete.py` is a file that a hypothetical user should launch in order to complete the task of running the relaxation of a structure.
The submission structure is code agnostic, demonstrating the first proof-of-concept of a common workflow interface.

The submission requires the call of the method `get_builder` of the `<Code>RelaxInputsGenerator`. This methods accepts in inputs:
* `structure`. The structure to be relaxed, an AiiDA `StructureData`

* `calc_engines`. A python dictionary containing the code and computational resources to use for completing the task. Some implementations might require more then one step (eventually code) to complete the relaxation.

* `protocol`. With the name protocol we mean a string that summarizes a certain set of inputs of the AiiDA process to be submitted and intends to offer a desired balance of accuracy and efficiency. For each plugin, at least, three protocols are available:

  * “fast” = return in a quick way a result that may not be reliable
  * “moderate” = reliable result (could be published), but no emphasis on convergence
  * “precise” = an high level of accuracy

  Documenetation of specifications of each protocol for each code is ...

* `relaxation_type`. RelaxType, HERE NOT SURE WHAT WE WANT. At the moment we accept only attributes of RelaxType.

* `threshold_forces`. A python `float` indicating the target threshold for the forces in eV/Å. Optional. If not specified, the developers might think to add it to the protocol specifications, or at least write in the documentation what is the default of their code.

* `threshold_stress`. A python `float` indicating the target threshold for the stress in eV/Å^3. Optional. If not specified, the developers might think to add it to the protocol specifications, or at least write in the documentation what is the default of their code.

The builder obtained from `get_builder` is ready to be submitted.

This `submission_templete.py` file also show the methods of the inputs generator that help to obtain the available options. For instance there is a method to list the available protocols, relaxation_types and so on.

The outputs of the submitted workchain, are standardized among different codes. The expecte outputs are also listed in `submission_templete.py`.

For developers, there is a page `Relaxation of a structure` explaining all the details of the implementation.
