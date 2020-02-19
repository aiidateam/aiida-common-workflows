# Relaxation WorkChain common interface

This folder collects the files required to illustrate the concept of the common interface for the test case of a Relaxation WorkChain.

The file submission_siesta.py is a file that an hypotetical user should launch in order to complete the task of running the struction relaxation a structure, but without the need to specify all the inputs node of a `SiestaRelaxWorkChain`. It is in fact the method `get_builder` of the class `SiestaRelaxationInputsGenerator` to suggest inputs according to a `protocol`.

This file should be the reference for all the plugins developers in order to implement their own `MyPluginRelaxationInputsGenerator`. It sets the standards for the sintax and illustrates the methods we expect in that class.

Please note this is just a prrof of concept. SiestaRelaxWorkChain do not exist or either SiestaRelaxationInputsGenerator does.

Open questions (to be discussed):
* Implementation of a method that suggests some computational resources (to be placed in `job_engines` dict)
  e.g. given a structure, how many nodes to use? This could also probably be outside of the MyPluginRelaxationInputsGenerator.

* At the moment to generate the builder we pass everything in the get_builder. One could argue that have separates methods
  (like MyPluginRelaxationInputsGenerator.set_job_engines(), MyPluginRelaxationInputsGenerator.set_protocol()) could be better.
  The latter is less nice, but useful if we can ask something to the class based on some preliminary information?
  E.g. if you want to take the default threshold_stress of the protocol you chose, and divide it by 10, by passing all parameters
  in one shot you need to know how the protocol internally works. It's true that in this case you probably will modify this in the 
  builder you get in the end? Even if, for these global common parameters, where to change them might differ between plugins.
  Or maybe you can have a method to sugget a number of machines given the structure and the computer? (see point above).

* Which energy in output?
  The total energy is not necessarily defined in a code-independent way (or with a properly defined zero). At least
  we should make sure that the quantity returned is such that its partial derivative with respect to the change of the 
  coordinate i of atom j is the force of the i-th coordinate on the atom j.
  Also it is important to be aware that the energies obtained running 

* We need to discuss at which level to introduce the possibility for the user to have minimal choice on the electronics of the calculation.
  PBE or LDA? Spin or not spin? We could independently have different protocols ("standard-LDA", "standard-spin-LDA", "fast-PBE") if we think
  that is important to have very different parameters for various cases (for instance I want more k-points in a magnetic calculation).
  Alternativly we could add flags to the GUI, or, in other words, to pass more parameters to get_builder.

Further possible options:
* Return dictionary of inputs instead of builder

