# aiida-common-workflows
A repository to collect ideas and first implementations for common workflow interfaces across materials science codes and plugins.

The idea consists in achiving a common interface for different codes at the level of protocol selections. For a specific task (for instance the relaxation of a structure), we agreed on the sintax to pass to a function that return a builder containing the inputs required for the specific task. This function is a method of a class (`CodeTaskInputGenerator`) with other functionalities; for instance it is usefull to have methods reeturning information about the possible potocols available for the specific task.

Taking the example of the structure relaxation, a line of the kind:

    generator = SiestaRelaxationInputsGenerator()
    builder = generator.get_builder(structure, protocol, relaxation_type)

Returns a builder of the `SiestaRelaxWorkChain` with inputs following a specific `protocol` and `relaxation_type`.
A similar string, but using a `QuantumEspressoRelaxationInputsGenerator()` would return inputs for the `QuantumEspressoRelaxWorkChain`. More details on the specific case are in the folder RelaxWorkChain.

The `protocol` specifications are code-dependent, but the common interface is the first step towards the creation of a GUI, where a user can select to run a specific task chosing a code, a protocol and few other input strings.

This repository will also host discussions about the idea to have standardized outputs among different code for a specific task. For instance the idea to call `relaxed_structure` the output node containing the final structure obtained after a relaxation.
