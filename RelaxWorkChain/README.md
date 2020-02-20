# Relaxation WorkChain common interface

This folder collects the files required to illustrate the concept of the common interface for the test case of a Relaxation WorkChain.

The file `submission_siesta.py` is a file that a hypotetical user should launch in order to complete the task of running the relaxation a structure, but without the need to specify all the input nodes of a `SiestaRelaxWorkChain`. 
These inputs are instead suggested by the `get_builder` method of the class `SiestaRelaxationInputsGenerator`, according to internal logic that can be selected via the `protocol` (e.g., to specify that we want a very converged calculation, or one uncoverged that can run very fast).

This file should be the reference for all the plugins developers in order to implement their own `MyPluginRelaxationInputsGenerator`. It sets the standards for the syntax and illustrates the methods we expect in that class.

Please note this is just a proof of concept, at this stage. Not even the SiestaRelaxWorkChain (in the sense presented in this folder) exists.

Open questions (to be discussed):

* Implementation of a method that suggests some computational resources (to be placed in `job_engines` dict).
  E.g. given a structure, how many nodes to use? This could also probably be outside of the `MyPluginRelaxationInputsGenerator`.

* At the moment to generate the builder we pass everything in the `get_builder`. One could argue that have separate methods
  (like `MyPluginRelaxationInputsGenerator.set_job_engines()`, `MyPluginRelaxationInputsGenerator.set_protocol()`) could be better.
  The latter is less nice, but useful if we can ask something to the class based on some preliminary information.
  E.g., if you want to take the default `threshold_stress` of the protocol you chose, and divide it by 10, by passing all parameters
  in one shot, you need to know how the protocol internally works. It's true that in this case you probably will modify this in the 
  builder you get in the end, though... Even if, for these global common parameters, where to change them might differ between plugins.

  Or maybe you can have a method to suggest a number of machines given the structure and the computer? (see point above).

* Which energy in output?
  The total energy is not necessarily defined in a code-independent way (or with a properly defined zero). At least
  we should make sure that the quantity returned is such that its partial derivative with respect to the change of the 
  coordinate `i` of atom `j` is the `i`-th coordinate of the force on the atom `j`.
  Also, it is important to be aware that the energies obtained running calculations at different volumes with protocols, might 
  not be comparable. For instance, the number of k-points might be chosen by the protocol to have a constant density of k-points in reciprocal space. Therefore, the k-point grid might depend on the volume, resulting in 
  equations of states with discontinuities if (as it is always the case) we are not perfectly converged. However, this can be solved by stating that the equation of state should not be implemented using this common workflow; rather, we will define a different generic property to be computed, the Equation of State, and define an API for an EOSInputGenerator for it.

* We need to discuss at which level to introduce the possibility for the user to have minimal choice on the electronics of the calculation.
  E.g., PBE or LDA? Spin or not spin? We could independently have different protocols ("standard-LDA", "standard-spin-LDA", "fast-PBE") if we think
  that is important to have very different parameters for various cases (for instance I want more k-points in a magnetic calculation).
  Alternatively, we could add flags to the GUI, or, in other words, to pass more parameters to get_builder.

* We need to clarify which outputs are optional (see current suggestion in the code example). We need to decide if the WorkChain is allowed to return additional "unexpected" nodes.
  Maybe it is ok, and maybe we should define a prefix `custom_*`. Reason: if a workchain returns for instance `number_of_steps`, and in the future we decide to make this part of the standard but with a different syntax/schema, we would have problems - if we call it instead `custom_number_of_steps`, this name will never clash with future extensions of the possible outputs. 

