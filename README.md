# aiida-common-workflows
A repository to collect ideas and first implementations for common workflow interfaces across materials science codes and plugins.

The aim of the project consists in achieving a common interface for different codes to compute in an automated way common materials properties.

For a specific task (for instance the relaxation of a structure), we agree on the API of a "builder factory" (named for instance following the pattern `<Code><Task>InputGenerator`), i.e. a python class that is able to return an AiiDA builder containing the required inputs to submit an AiiDA process (typically a WorkChain) computing the property. With API we mean the name and signature of the methods that this "builder factory" has and its expected inputs. In other words, a line of the kind:

```
input_generator = <Code><Task>InputGenerator()
builder = inputs_generator.get_builder(par1, par2, ...)
```

should return a builder for an AiiDA process able to complete the task `<Task>` and the inputs of `get_builder` (indicated in the example with par1, par2, ...) must be the same for each `<Code>` (given a `<Task>`).

In addition to a method `get_builder`, the class `<Code><Task>InputGenerator` has additional methods, for instance to return information about the possible options available for the specific task.

Finally, the AiiDA process to be run (whose builder is return by get_builder) should return standardized outputs among different codes, for a specific task. For instance, in the case of the relaxation of a structure, all should return a StructureData node, with an output return link labeled relaxed_structure, with the final structure obtained after a relaxation.

More information for developer can be found on the wiki of this repository.
