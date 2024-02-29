Common Equation of State Workflow
---------------------------------

The Equation of State (EoS) workflow automatically runs relaxation workflows at several volumes, computing the final total energy at each volume.
The inputs for the relaxation can be defined in a code-agnostic way, making use of the common interface of the :ref:`common relax workflow <relax-inputs>`.
Relaxation types with variable volume are forbidden.
To allow full flexibility on the inputs, code-dependent overrides can be specified through the input port ``sub_process`` (see below).

Submission script template
..........................

A typical script for the submission of common EoS workflow could look something like the following:

.. code:: python

    from aiida.orm import List, Dict
    from aiida.engine import submit
    from aiida_common_workflows.plugins import WorkflowFactory

    cls = WorkflowFactory('common_workflows.eos')

    inputs = {
        'structure': structure,
        'scale_factors': List(list=[0.90, 0.94, 0.96, 1, 1.04, 1.06, 1.08]),
        'generator_inputs': {  # code-agnostic inputs for the relaxation
            'engines': engines,
            'protocol': protocol,
            'relax_type': relax_type,
            ...
        },
        'sub_process_class': 'common_workflows.relax.<implementation>',
        'sub_process' : {  # optional code-dependent overrides
            'parameters' : Dict(dict={...})
            ...
        },
    }

    submit(cls, **inputs)

The inputs of the EoS workchain are detailed below.


Inputs
......

* ``structure``.
  (Type: an AiiDA `StructureData`_ instance, the common data format to specify crystal structures and molecules in AiiDA).
  The base structure whose volume will be rescaled by ``scale_factors`` (see next input).
  A relaxation is performed on each re-scaled structure in order to create the EoS.

* ``scale_factors``.
  (Type: a list of Python float or int values, wrapped in the AiiDA `List`_ data type).
  The scale factors at which the volume and total energy of the structure should be computed.
  This input is optional since the scale factors can be set in an alternative way (see next input).

* ``scale_count`` and ``scale_increment``.
  (Type: an AiiDA `Int`_ and `Float`_ respectively, the data format devoted to the specification of integers and floats in AiiDA).
  These two inputs can be used together to set the scaling factors for the EoS.
  The ``scale_count`` indicates the number of points to compute for the EoS and the ``scale_increment`` sets the relative difference between consecutive scaling factors.
  The scaling factors will always be centered around ``1``.
  If the ``scale_factors`` port is specified, these two inputs are ignored.
  The default for ``scale_count`` is ``Int(7)`` and for ``scale_increment`` is ``Float(0.02)``.

* ``sub_process_class``.
  (Type: valid workflow entry point for one common relax implementation).
  The quantum engine that will be used for the relaxation is determined through the ``sub_process_class`` input, that must be a valid workflow entry point for a common relax implementation.
  Referring to the submission template above, the ``<implementation>`` in the string ``'common_workflows.relax.<implementation>'`` should be replaced with the corresponding entry point name of a quantum engine, for instance ``common_workflows.relax.quantum_espresso``.
  To see a list of all available entry points, call ``verdi plugin list aiida.workflows``.
  Any entry point that starts with ``common_workflows.relax.`` can be used.

* ``generator_inputs``.
  (Type: a Python dictionary).
  This input namespace is dedicated to the specifications of the common relax inputs.
  A full list of the allowed inputs are described in the :ref:`dedicated section <relax-inputs>`.
  Only the ``structure`` input is not allowed in the ``generator_inputs``, since it is selected for each volume by the workflow.
  Also, the ``relax_types`` are limited to the options with fixed volume.


* ``sub_process``.
  (Type: a Python dictionary).
  This input name-space hosts code-dependent inputs that can be used to override inputs generated through the ``generator_inputs``.
  The specified keys must be accepted input port of the corresponding ``sub_process_class`` workflow.

.. note::
  The relaxation at the various volumes are not all performed in parallel.
  The relaxation of the structure at the first ``scaling_factor`` is performed first.
  Then all the other relaxations are computed in parallel using the first relaxation as :ref:`reference_workchain input <relax-ref-wc>`.
  This ensures to have comparable energies among the various structures.



Outputs
.......

The EoS workchain simply returns for each relaxation run a structure (as AiiDA `StructureData`_ under the namespace ``structures``) and an energy (in eV, as AiiDA `Float`_ and under the namespace ``total_energies``).
If returned by the underline common relax workflow, also the total magnetization for each relaxation is returned (in μB, as `Float`_ and under the namespace ``total_magnetizations``).

A template script to retrieve the results follows:

.. code:: python

    from aiida.common import LinkType

    node = load_node(<IDN>) # <IDN> is an identifier (PK, uuid, ..) of a completed EoS workchain

    outputs = node.base.links.get_outgoing(link_type=LinkType.RETURN).nested()

    volumes = []
    energies = []
    magnetizations = []

    for index in outputs['total_energies'].keys():
        volumes.append(outputs['structures'][index].get_cell_volume())
        energies.append(outputs['total_energies'][index].value)
        try:
            total_magnetization = outputs['total_magnetizations'][index].value
        except KeyError:
            total_magnetization = None
        magnetizations.append(total_magnetization)

CLI
...

The use of the CLI for the submission of a common workflow is reported in the :ref:`main page <how-to-submit>` of this documentation.
For the eos workflow:

.. code:: console

    acwf launch eos <OPTIONS> -- <ENGINE>

The available ``<ENGINE>`` and ``<OPTIONS>`` are the same of the :ref:`relaxation CLI <relax-cli>`, with the exception of the ``-P`` option and a limitation on the allowed relaxation types.


.. _StructureData: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#structuredata
.. _Int: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#core-data-types
.. _Float: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#core-data-types
.. _List: https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#core-data-types
