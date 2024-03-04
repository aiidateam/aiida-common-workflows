=============================
AiiDA common workflows (ACWF)
=============================

**aiida-common-workflows version:** |release|

.. toctree::
   :maxdepth: 2
   :hidden:

   workflows/base/index
   workflows/composite/index

.. image:: images/calculator.jpg
   :width: 100%
   :alt: The AiiDA common workflows (ACWF) project
   :align: right

The AiiDA common workflows (ACWF) project provides computational workflows, implemented in `AiiDA`_, to compute various material properties using any of the quantum engines that implement it.
The distinguishing feature is that the interfaces of the AiiDA common workflows are uniform, independent of the quantum engine that is used underneath to perform the material property simulations.
These common interfaces make it trivial to switch from quantum engine.
In addition to the common interface, the workflows provide input generators that automatically define the required inputs for a given task and desired computational precision.

The common workflows can be subdivided into two categories:

.. grid:: 1 2 2 2
   :gutter: 2

   .. grid-item-card:: :fa:`cogs;mr-1` **Base common workflows**
      :text-align: center
      :shadow: md

      Workflows for basic material properties that define a common interface and are implemented for various quantum engines.

      +++++++++++++++++++++++++++++++++++++++++++++

      .. button-ref:: workflows/base/index
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         To the base workflows

   .. grid-item-card:: :fa:`sitemap;mr-1` **Composite common workflows**
      :text-align: center
      :shadow: md

      Higher-level workflows that reuse base common workflows in order to maintain the common interface.

      +++++++++++++++++++++++++++++++++++++++++++++

      .. button-ref:: workflows/composite/index
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         To the composite workflows



.. _installation:

************
Installation
************

The Python package can be installed from the Python Package index (PyPI) or directly from the source:
The recommended method of installation is to use the Python package manager ``pip``:

.. code-block:: console

    $ pip install aiida-common-workflows

This will install the latest stable version that was released to PyPI.
Note that this will not install any of the plugin packages that are required to run any of the common workflow implementations.
To install all plugin packages that implement a common workflow, run the install with the ``all_plugins`` extra:

.. code-block:: console

    $ pip install aiida-common-workflows[all_plugins]

Alternatively, you can choose a specific plugin to prevent having to install all plugin packages, for example:

.. code-block:: console

    $ pip install aiida-common-workflows[quantum_espresso]

will install the package plus the dependencies that are required to run the implementation for Quantum ESPRESSO.
The available extras are ``abinit``, ``bigdft``, ``castep``, ``cp2k``, ``fleur``, ``gaussian``, ``gpaw``, ``nwchem``, ``orca``, ``quantum_espresso``, ``siesta``, ``vasp`` and ``wien2k``.

To install the package from source, first clone the repository and then install using ``pip``:

.. code-block:: console

    $ git clone https://github.com/aiidateam/aiida-common-workflows
    $ pip install -e aiida-common-workflows

The ``-e`` flag will install the package in editable mode, meaning that changes to the source code will be automatically picked up.

To work with ``aiida-common-workflows``, a configured AiiDA profile is required.
Please refer to `AiiDA's documentation <https://aiida.readthedocs.io/projects/aiida-core/en/latest/intro/get_started.html>`_ for detailed instructions.


.. _how-to-submit:

*******************************
How to use the common workflows
*******************************

To launch a common workflow, there are two main methods:

 * Use the built-in command line interface (CLI) utility
 * Write a custom launch script

The first option is the simplest option to get started, however, it is not necessarily available for all common workflows and it does not expose the full functionality.
For example, if you want to optimize the geometry of a crystal structure using the CLI, you can run the following command:

.. code:: console

    acwf launch relax -S <STRUCTURE> -X <CODE>  -- <ENGINE>

Here, the ``<STRUCTURE>`` should be replaced with the `AiiDA identifier`_ of the `StructureData`_ that needs to be optimized, ``<CODE>`` with the identifier of the `Code`_ that should be used and ``<ENGINE>`` the entry point name of the quantum engine whose workflow implementation should be employed.
To determine what engine implementations are available, run the command with the ``--help`` flag:

.. code:: console

    acwf launch relax --help

This will also provide information of all other available options.
Although this command already provides quite a number of options in order to facilitate various use cases, it can never expose the full functionality.
If more flexibility is required, it is advised to write a custom launch script, for example:

.. code:: python

    from aiida.engine import submit
    from aiida_common_workflows.plugins import WorkflowFactory

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')  # Load the relax workflow implementation of choice.

    structure = <STRUCTURE>  # A `StructureData` node representing the structure to be optimized.
    engines = {
        'relax': {
            'code': <CODE>,  # An identifier of a `Code` configured for the `quantumespresso.pw` plugin
            'options': {
                'resources': {
                    'num_machines': 1,  # Number of machines/nodes to use
                },
                'max_wallclock_seconds': 3600,  # Number of wallclock seconds to request from the scheduler for each job
            }
        }
    }

    builder = RelaxWorkChain.get_input_generator().get_builder(structure, engines)
    submit(builder)

The script essentially consists of four steps:

 1. Load the workflow implementation for the desired quantum engine based on its `entry point name`_.
    To determine the available implementations, you can run the command ``verdi plugin list aiida.workflows``.
    Any entry point that starts with ``common_workflows.relax.`` can be used to run the common relax workflow.
    The suffix denotes the quantum engine that underlies the implementation.
 2. Define the required ``structure`` and ``engines`` inputs.
 3. Retrieve the workflow builder instance for the given inputs.
    This ``get_builder`` method will return a `process builder instance`_ that has all the necessary inputs defined based on the protocol (see next section) of the input generator.
    At this point, a user is free to change any of these default inputs.
 4. All that remains is to ``submit`` the builder to the daemon and the workflow will start to run (if the daemon is running).


***************
Input protocols
***************

Each base common workflow provides an input generator that implements the common interface.
The generator provides the ``get_builder`` method, which for a minimum set of required inputs,
returns a process builder with all the required inputs defined and therefore is ready for submission.
The inputs are determined by a "protocol" which represents the desired precision.
For example, the common relax workflow provides at least the three protocols ``fast``, ``moderate`` and ``precise``.
The ``precise`` protocol will select inputs that will yield calculations of a higher precision, at a higher computational cost.
The ``fast`` protocol will be computationally cheaper but will also have reduced precision.

To determine what protocols are available for a given workflow, you can call the ``get_protocol_names`` method in the input generator, for example:

.. code:: python

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')
    RelaxWorkChain.get_input_generator().get_protocol_names()

The default protocol can be determined as follows:

.. code:: python

    RelaxWorkChain.get_input_generator().get_default_protocol_name()

To use a different protocol for the generation of the inputs, simply pass it as an argument to the ``get_builder`` method:

.. code:: python

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')
    builder = RelaxWorkChain.get_input_generator().get_builder(structure=..., engines=..., protocol='precise')

.. note::

    The inputs determined by the protocols are set on the builder and therefore can be modified before submission.
    These inputs are code dependent and their modification requires knowledge of the underlying quantum engine implementation of the base common workflow.



***********
How to cite
***********

If you use the workflow of this package, please cite the paper in which the work is presented: `S. P. Huber et al., npj Comput. Mater. 7, 136 (2021)`_.

In addition, if you run the common workflows, please also cite the AiiDA engine that manages the simulations and stores the provenance:

   * Main AiiDA paper: `S. P. Huber et al., Scientific Data 7, 300 (2020)`_

   * AiiDA engine: `M. Uhrin et al., Comp. Mat. Sci. 187 (2021)`_


You should also cite the quantum engines whose implementations are used; you can check the `README of the project`_ for a summary table of references for each quantum engine.



.. _AiiDA: http://www.aiida.net
.. _AiiDA identifier: https://aiida-core.readthedocs.io/en/latest/topics/cli.html#topics-cli-identifiers
.. _StructureData: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#structuredata
.. _Code: https://aiida-core.readthedocs.io/en/latest/howto/run_codes.html#how-to-setup-a-code
.. _entry point name: https://aiida-core.readthedocs.io/en/latest/topics/plugins.html#what-is-an-entry-point)
.. _process builder instance: https://aiida-core.readthedocs.io/en/latest/topics/processes/usage.html?highlight=ProcessBuilder#process-builder
.. _S. P. Huber et al., npj Comput. Mater. 7, 136 (2021): https://doi.org/10.1038/s41524-021-00594-6
.. _README of the project: https://github.com/aiidateam/aiida-common-workflows/blob/master/README.md
.. _S. P. Huber et al., Scientific Data 7, 300 (2020): https://doi.org/10.1038/s41597-020-00638-4
.. _M. Uhrin et al., Comp. Mat. Sci. 187 (2021): https://doi.org/10.1016/j.commatsci.2020.110086
