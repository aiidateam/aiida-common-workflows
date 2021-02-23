# aiida-common-workflows
This package provides reusable workflows with common interfaces, implemented in [AiiDA](https://www.aiida.net), to compute material properties using various quantum engines.
The common workflows make it easy to compute a material property for a variety of quantum engines.
The workflows and their protocols are implemented by experts of the various quantum engines guaranteeing results of a desired precision.
On top of that, the workflows report their results according to the same unified schema, making comparing and reusing results trivial.
For more details, please refer to the original [publication (doi:)]().

## Available common workflows
The common workflows can be subdivided into two categories:

 1. Base common workflows
 2. Composite common workflows

The base common workflows are those that define a single common interface for a workflow that computes a common material property or performs a common operation.
This interface can then be implemented for various quantum engines.
The resulting common workflow can then be reused as a modular block to create higher-level workflows.
As long as this composite workflow uses exclusively base common workflows, its interface will also be fully agnostic of the quantum engine used.

The following table shows the currently available base common workflows and the entry point prefix, as well as the entry point name suffix for each quantum engine that implements it.

Workflow  |  Entry point prefix        | Description                                  | ABINIT   | BigDFT   | CASTEP   | CP2K   | FLEUR   | Gaussian   | NWChem   | ORCA   | Quantum ESPRESSO   | SIESTA   | VASP
--------- | -------------------------- | -------------------------------------------- |--------- | -------- | -------- | ------ | ------- | ---------- | -------- | ------ | ------------------ | -------- | -------
Relax     | `common_workflows.relax.`  | Optimize the geometry of a solid or molecule | `abinit` | `bigdft` | `castep` | `cp2k` | `fleur` | `gaussian` | `nwchem` | `orca` | `quantum_espresso` | `siesta` | `vasp`

Using the base common workflows listed above, the following composite common workflows are provided by this package:

Workflow                 | Entry point name                      | Base common workflows  | Description
------------------------ | ------------------------------------- | ---------------------- | ----------------------------------------------------------------
Equation of state (EOS)  | `common_workflows.eos`                | Relax                  | Computes the equation of state of a solid.
Dissociation curve (DC)  | `common_workflows.dissociation_curve` | Relax                  | Computes the dissociation curve of a diatomic molecule.

## How to use the common workflows
To launch a common workflow, there are two main methods:

 * Use the built-in command line interface (CLI) utility
 * Write a custom launch script

The first option is the simplest option to get started, however, it is not necessarily available for all common workflows and it does not expose the full functionality.
For example, if you want to optimize the geometry of a crystal structure using the CLI, you can run the following command:

    aiida-common-workflows launch relax -S <STRUCTURE> -X <CODE> <ENGINE>

Here, the `<STRUCTURE>` should be replaced with the [AiiDA identifier](https://aiida-core.readthedocs.io/en/latest/topics/cli.html#topics-cli-identifiers) of the [`StructureData`](https://aiida-core.readthedocs.io/en/latest/topics/data_types.html#structuredata) that needs to be optimized, `<CODE>` with the identifier of the [`Code`](https://aiida-core.readthedocs.io/en/latest/howto/run_codes.html#how-to-setup-a-code) that should be used and `<ENGINE>` the entry point name of the quantum engine whose workflow implementation should be employed.
To determine what engine implementations are available, run the command with the `--help` flag:

    aiida-common-workflows launch relax --help

This will also provide information of all other available options.
Although this command already provides quite a number of options in order to facilitate various use cases, it can never expose the full functionality.
If more flexibility is required, it is advised to write a custom launch script, for example:

```python
from aiida.engine import submit
from aiida.plugin import WorkflowFactory

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
```

The script essentially consists of four steps:

 1. Load the workflow implementation for the desired quantum engine based on its [entry point name](https://aiida-core.readthedocs.io/en/latest/topics/plugins.html#what-is-an-entry-point).
    To determine the available implementations, you can run the command `verdi plugin list aiida.workflows`.
    Any entry point that starts with `common_workflows.relax.` can be used to run the common relax workflow.
    The suffix denotes the quantum engine that underlies the implementation.
 2. Define the required `structure` and `engines` inputs.
 3. Retrieve the workflow builder instance for the given inputs.
    This `get_builder` method will return a [process builder instance](https://aiida-core.readthedocs.io/en/latest/topics/processes/usage.html?highlight=ProcessBuilder#process-builder) that has all the necessary inputs defined based on the protocol of the input generator.
    At this point, you are free to change any of these default inputs.
 4. All that remains is to `submit` the builder to the daemon and the workflow will start to run (if the daemon is running).


## Input protocols
Each base common workflow provides an input generator that implements the common interface.
The generator provides the `get_builder` method, which for a minimum set of required inputs, returns a process builder with all the required inputs defined and therefore is ready for submission.
The inputs are determined by a "protocol" which represents the desired precision.
For example, the common relax workflow provides at least the three protocols `fast`, `moderate` and `precise`.
The `precise` protocol will select inputs that will yield calculations of a higher precision, at a higher computational cost.
The `fast` protocol will be computationally cheaper but will also have reduced precision.

To determine what protocols are available for a given workflow, you can call the `get_protocol_names` method in the input generator, for example:

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')
    RelaxWorkChain.get_input_generator().get_protocol_names()

The default protocol can be determined as follows:

    RelaxWorkChain.get_input_generator().get_default_protocol_name()

To use a different protocol for the generation of the inputs, simply pass it as an argument to the `get_builder` method:

    RelaxWorkChain = WorkflowFactory('common_workflows.relax.quantum_espresso')
    RelaxWorkChain.get_input_generator().get_builder(structure=..., engines=..., protocol='precise')


## How to cite
If you use the workflow of this package, please cite the [original paper (doi:)]().
In addition, one should cite the quantum engines whose implementations are used.

Engine           | DOIs or URLs to be cited
---------------- | ----------------------------
ABINIT           |
BigDFT           |
CASTEP           |
CP2K             |
FLEUR            |
Gaussian         |
NWChem           |
ORCA             |
Quantum ESPRESSO |
SIESTA           |
VASP             |
