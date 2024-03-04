Common Relax Workflow
---------------------

The common relax workflow performs a geometric optimization of a molecule or extended system towards the most energetically favorable configuration.
It defines a common interface that is currently implemented by eleven quantum engines: Abinit, BigDFT, CASTEP, CP2K, FLEUR, Gaussian, NWChem, ORCA, Quantum ESPRESSO, Siesta, VASP.
Note that the ORCA and Gaussian implementations only support the optimization of molecules.
On this page you will find generic information on how to use any of these implementations of the common relax workflow.
The links in the table below provide detailed information on the input generators and any important information regarding the implementation of the individual implementations themselves.

.. toctree::
   :maxdepth: 1

   implementations/abinit
   implementations/bigdft
   implementations/castep
   implementations/cp2k
   implementations/fleur
   implementations/gaussian
   implementations/nwchem
   implementations/orca
   implementations/quantum_espresso
   implementations/siesta
   implementations/vasp

In the initial page of this documentation the general instructions for the :ref:`submission of a common workflow <how-to-submit>` are presented, covering both the use of the built-in command line interface (CLI) and custom submission scripts.
Since the CLI does not expose the full functionalities of the interface, this section focuses on the creation of submission scripts and explains how to have full control on the relaxation process through the common interface.
The CLI is explained at the end of the section.

.. _relax-inputs:

Submission script template
..........................

A typical script for the submission of common relax workflow could look something like the following:

.. code:: python

    from aiida.engine import submit
    from aiida_common_workflows.plugins import WorkflowFactory

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.<implementation>')  # Load the relax workflow implementation of choice.

    # DEFINITION OF <RELAXATION INPUTS>

    input_generator = RelaxWorkChain.get_input_generator()
    builder = input_generator.get_builder(<RELAXATION INPUTS>)
    submit(builder)


The quantum engine that will be used for the relaxation is determined by the entry point that is passed to the ``WorkflowFactory``.
To select a particular quantum engine, you should replace ``<implementation>`` in the string ``'common_workflows.relax.<implementation>'`` with the corresponding entry point name of the quantum engine.
To see a list of all available entry points, call ``verdi plugin list aiida.workflows``.
Any entry point that starts with ``common_workflows.relax.`` can be used, for example ``common_workflows.relax.quantum_espresso`` corresponds to the implementation using Quantum ESPRESSO.

Inputs
...........


The ``RelaxWorkChain.get_input_generator().get_builder`` method takes a number of required and optional arguments (referenced as ``<RELAXATION INPUTS>`` in the example submission script), which are listed below.
Only ``structure`` and ``engines`` can be specified as a positional argument, all others have to be defined as a keyword argument.

* ``structure``. (Type: an AiiDA `StructureData`_ instance, the common data format to specify crystal structures and molecules in AiiDA).
  The structure to relax.

* ``engines``. (Type: a Python dictionary).
  It specifies the codes and the corresponding computational resources for each step of the relaxationi process. A typical example is:

  .. code:: python

        engines = {
              'relax': {
                  'code': <CODE>,  # An identifier (PK, UUID or full label) of a `Code` configured for the selected quantum engine plugin, e.g., ``'pw-v6.5@localhost'`.
                  'options': {
                      'resources': {
                          'num_machines': 1,  # Number of machines/nodes to use
                      },
                      'max_wallclock_seconds': 3600,  # Number of wallclock seconds to request from the scheduler for each job
                  }
              }
          }

  Typically one single executable is sufficient to perform the relaxation.
  However, there are cases in which two or more codes in the same simulation package are required to achieve the final goal, as for example in the case of FLEUR.
  In order to explore the steps of the relaxation process, the ``input_generator`` provides an inspection method:

  .. code:: python

    input_generator.get_engine_types()

  For each ``engine_type`` (for instance ``inpgen`` of FLEUR), details on the required code and resources can be obtained with:

  .. code:: python

    input_generator.get_engine_type_schema("inpgen")


* ``protocol``. (Type: a Python string).
  A single string summarizing the computational accuracy of the underlying DFT calculation and relaxation algorithm.
  Three protocol names are defined and implemented for each code: ``fast``, ``moderate`` and ``precise``.
  The details of how each implementation translates a protocol string into a choice of parameters is code dependent, or more
  specifically, they depend on the implementation choices of the corresponding AiiDA plugin.
  However the chosen parameters respect the meaning of the corresponding string:

    * ``fast``: a possibly unconverged (but still meaningful) run that executes rapidly for testing.
    * ``moderate``: a safe choice for prototyping and preliminary studies.
    * ``precise``: uses parameters that might result in an computationally expensive simulation but provides well converged results.

  More details on the parameter choices for the eleven implementations supporting the relax common are reported in the supplementary material of `S. P. Huber et al., npj Comput. Mater. 7, 136 (2021)`_.
  Three inspections method are implemented for the protocol specifications:

  .. code:: python

    input_generator.get_protocol_names()
    input_generator.get_protocol('fast')  # Can replace 'fast' with any of the other available protocols
    input_generator.get_default_protocol_name()


* ``relax_type``. (Type: a Python string).
  The type of relaxation to perform, ranging from the relaxation of only atomic coordinates to the full cell relaxation for extended systems.
  The complete list of supported options is: ‘none’,‘positions’, ‘volume’, ‘shape’, ‘cell’, ‘positions_cell’, ‘positions_volume’, ‘positions_shape’.
  Each name indicates the physical quantities allowed to relax. For instance, ‘positions_shape’ corresponds to a relaxation where both the shape of the cell and the atomic coordinates are relaxed, but not the volume; in other words, this option indicates a geometric optimization at constant volume.
  On the other hand, the ‘shape’ option designates a situation when the shape of the cell is relaxed and the atomic coordinates are rescaled following the variation of the cell, not following a force minimization process.
  The term "cell" is short-hand for the combination of ‘shape‘ and ‘volume’.
  The option ‘none’ indicates the possibility to calculate the total energy of the system without optimizing the structure.
  Not all the described options are supported by each code involved in this work; only the options ‘none’ and ‘positions’ are shared by all the eleven codes.
  To explore the supported relaxation types for each implementation an inspection method is available:

  .. code:: python

    input_generator.get_relax_types()


* ``threshold_forces``. (Type: a Python float).
  A real positive number indicating the target threshold for the forces in eV/Å.
  If not specified, the protocol specification will select an appropriate value.

* ``threshold_stress``. (Type: a Python float).
  A real positive number indicating the target threshold for the stress in eV/Å^3.
  If not specified, the protocol specification will select an appropriate value.

* ``electronic_type``.   (Type: a Python string).
  An optional string to signal whether to perform the simulation for a metallic or an insulating system.
  It accepts only the ‘insulator’ and ‘metal’ values.
  This input is relevant only for calculations on extended systems.
  In case such option is not specified, the calculation is assumed to be metallic which is the safest assumption.
  An exact understanding of the difference between ‘insulator’ and ‘metal’ calculations for each supported quantum engine can be achieved reading the supplementary material of `S. P. Huber et al., npj Comput. Mater. 7, 136 (2021)`_.
  It must be noted that several implementations ignore the passing of this option since do not require special input parameters for  ‘insulator’ or ‘metal’ calculations.
  To explore the supported electronic types for each implementation an inspection method is available:

  .. code:: python

    input_generator.get_electronic_types()


* ``spin_type``. (Type: a python string).
  An optional string to specify the spin degree of freedom for the calculation.
  It accepts the values ‘none’ or ‘collinear’. These will be extended in the future to include, for instance, non-collinear magnetism and spin-orbit coupling.
  The default is to run the calculation without spin polarization.
  To explore the supported spin types for each implementation an inspection method is available:

  .. code:: python

    input_generator.get_spin_types()


* ``magnetization_per_site``. (Type: Python None or a Python list of floats).
  An input devoted to the initial magnetization specifications.
  It accepts a list where each entry refers to an atomic site in the structure.
  The quantity is passed as the spin polarization in units of electrons, meaning the difference between spin up and spin down electrons for the site.
  This also corresponds to the magnetization of the site in Bohr magnetons (μB).
  The default for this input is the Python value None and, in case of calculations with spin, the None value signals that the implementation should automatically decide an appropriate default initial magnetization.
  The implementation of such choice is code-dependent and described in the supplementary material of the `S. P. Huber et al., npj Comput. Mater. 7, 136 (2021)`_.

.. _relax-ref-wc:

* ``reference_workchain.`` (Type: a previously completed ``RelaxWorkChain``, performed with the same code as the ``RelaxWorkChain`` created by ``get_builder``).
  When this input is present, the interface returns a set of inputs which  ensure  that  results of the new ``RelaxWorkChain`` (to be run) can be directly compared to the ``reference_workchain``.
  This is necessary to create, for instance, meaningful equations of state.



Outputs
...........

To allow direct comparison and cross-verification of the results, the outputs of ``RelaxWorkChain`` are standardized for all implementations and are defined as follows:

* ``forces``.
  The final forces on all atoms in eV/Å.
  (Type: an AiiDA ``ArrayData`` of shape N×3, where N is the number of atoms in the structure).

* ``relaxed_structure``.
  The structure obtained after the relaxation. It is not returned if the relax_type is ‘none’.
  (Type: AiiDA ``StructureData``).

* ``total_energy``.
  The total energy in eV associated to the relaxed structure (or initial structure in case no relaxation is performed).
  In general, even for calculations performed with the same code, there is no guarantee to have comparable energies in different runs if the numerical parameters determined by the input generator change (because, for instance, structures with different volumes are passed).
  However, in combination with the input argument ``reference_workchain``, energies from different relaxation runs become comparable, and their energy difference is well defined.
  (Type: AiiDA ``Float``).

* ``stress``.
  The final stress tensor in eV/Å^3.
  Returned only when a variable-cell relaxation is performed.
  (Type: AiiDA ``Float``).

* ``total_magnetization``.
  The total magnetization in μB (Bohr-magneton) units.
  Returned only for magnetic calculations.
  (Type: AiiDA ``Float``).


.. _relax-cli:

CLI
...

The use of the CLI for the submission of a common workflow is reported in the :ref:`main page <how-to-submit>` of this documentation.
For the relaxation workflow:

.. code:: console

    acwf launch relax <OPTIONS>  -- <ENGINE>

The available ``<ENGINE>`` are:

.. code:: console

    [abinit|bigdft|castep|cp2k|fleur|gaussian|orca|quantum_espresso|siesta|vasp]


A list of options follows:

.. code:: console

  -S, --structure                 An existing `StructureData` identifier, or a
                                  file on disk with a structure definition
                                  that can be parsed by `ase`.

  -X, --codes CODE ...            One or multiple codes identified by their
                                  ID, UUID or label. What codes are required
                                  is dependent on the selected plugin and can
                                  be shown using the `<ENGINE> --show-engines` option.
                                  If no explicit codes are specified, one will
                                  be loaded from the database based on the
                                  required input plugins. If multiple codes
                                  are matched, a random one will be selected.

  -p, --protocol                  [fast|moderate|precise]
                                  Select the protocol with which the inputs
                                  for the workflow should be generated.
                                  [default: fast]

  -r, --relax-type                [none|positions|volume|shape|cell|positions_cell|positions_volume|positions_shape]
                                  Select the relax type with which the
                                  workflow should be run.  [default:positions]

  -s, --spin-type                 [none|collinear|non_collinear|spin_orbit]
                                  Select the spin type with which the workflow
                                  should be run.  [default: none]

  --threshold-forces FLOAT        Optional convergence threshold for the
                                  forces. Note that not all plugins may
                                  support this option.

  --threshold-stress FLOAT        Optional convergence threshold for the
                                  stress. Note that not all plugins may
                                  support this option.

  -m, --number-machines VALUE ... Define the number of machines to request for
                                  each engine step.

  -n, --number-mpi-procs-per-machine VALUE ...  Define the number of MPI processes per
                                                machine to request for each engine step.

  -w, --wallclock-seconds VALUE ...  Define the wallclock seconds to request for
                                     each engine step.

  -d, --daemon                    Submit the process to the daemon instead of
                                  running it locally.

  --magnetization-per-site FLOAT ...   Optional list containing the initial spin
                                       polarization per site in units of electrons.

  -P, --reference-workchain WORKFLOWNODE    An instance of a completed workchain of the
                                            same type as would be run for the given
                                            plugin.


.. _StructureData: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#structuredata
.. _S. P. Huber et al., npj Comput. Mater. 7, 136 (2021): https://doi.org/10.1038/s41524-021-00594-6
