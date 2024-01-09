# AiiDA common workflows (ACWF) package: `aiida-common-workflows`
![AiiDA common workflows](docs/source/images/calculator.jpg)
<sup><sub>(Image © Giovanni Pizzi, 2021)</sub></sup>

The AiiDA common workflows (ACWF) project provides computational workflows, implemented in [AiiDA](https://www.aiida.net), to compute various material properties using any of the quantum engines that implement it.
The distinguishing feature is that the interfaces of the AiiDA common workflows are uniform, independent of the quantum engine that is used underneath to perform the material property simulations.
These common interfaces make it trivial to switch from quantum engine.
In addition to the common interface, the workflows provide input generators that automatically define the required inputs for a given task and desired computational precision.
For more information, please refer to the [online documentation](https://aiida-common-workflows.readthedocs.io/en/latest/).


## How to cite
If you use the workflow of this package, please cite the paper in which the work is presented:

> [S. P. Huber et al., npj Comput. Mater. 7, 136 (2021); doi:10.1038/s41524-021-00594-6](https://doi.org/10.1038/s41524-021-00594-6)

In addition, if you run the common workflows, please also cite:

1. The AiiDA engine that manages the simulations and stores the provenance:

   * Main AiiDA paper: [S.P. Huber et al., Scientific Data 7, 300 (2020)](https://doi.org/10.1038/s41597-020-00638-4)

   * AiiDA engine: [M. Uhrin et al., Comp. Mat. Sci. 187 (2021)](https://doi.org/10.1016/j.commatsci.2020.110086)

2. the quantum engine(s) that you will use. We provide below a table of references for your convenience.

Engine           | DOIs or URLs to be cited
---------------- | ----------------------------
ABINIT           | [10.1016/j.cpc.2016.04.003](https://doi.org/10.1016/j.cpc.2016.04.003) [10.1016/j.cpc.2019.107042](https://doi.org/10.1016/j.cpc.2019.107042) [10.1063/1.5144261](https://doi.org/10.1063/1.5144261)
BigDFT           | [10.1063/5.0004792](https://doi.org/10.1063/5.0004792)
CASTEP           | [10.1524/zkri.220.5.567.65075](https://doi.org/10.1524/zkri.220.5.567.65075)
CP2K             | [10.1002/wcms.1159](https://doi.org/10.1002/wcms.1159) [10.1063/5.0007045](https://doi.org/10.1063/5.0007045)
FLEUR            | [https://www.flapw.de](https://www.flapw.de)
Gaussian         | [see instructions here](https://gaussian.com/g09citation/)
GPAW             | [10.1103/PhysRevB.71.035109](https://doi.org/10.1103/PhysRevB.71.035109) [10.1088/0953-8984/22/25/253202](https://doi.org/10.1088/0953-8984/22/25/253202)
NWChem           | [10.1063/5.0004997](https://doi.org/10.1063/5.0004997)
ORCA             | [10.1002/wcms.81](https://doi.org/10.1002/wcms.81) [10.1002/wcms.1327](https://doi.org/10.1002/wcms.1327)
Quantum ESPRESSO | [10.1088/0953-8984/21/39/395502](https://doi.org/10.1088/0953-8984/21/39/395502) [10.1088/1361-648x/aa8f79](https://doi.org/10.1088/1361-648x/aa8f79)
SIESTA           | [10.1063/5.0005077](https://doi.org/10.1063/5.0005077) [10.1088/0953-8984/14/11/302](https://doi.org/10.1088/0953-8984/14/11/302)
VASP             | [10.1103/physrevb.54.11169](https://doi.org/10.1103/physrevb.54.11169)  [10.1103/physrevb.59.1758](https://doi.org/10.1103/physrevb.59.1758)
WIEN2k           | [10.1063/1.5143061](https://doi.org/10.1063/1.5143061)

## Examples of use

This AiiDA common workflows package was used as the core engine to run all simulations for the paper:

>  [E. Bosoni et al., *How to verify the precision of density-functional-theory implementations via reproducible and universal workflows*, **Nat. Rev. Phys. 6**, 45 (2024)](https://doi.org/10.1038/s42254-023-00655-3)

The corresponding scripts to run simulations and analyze the data can be found on the [`acwf-verification-scripts` GitHub repository](https://github.com/aiidateam/acwf-verification-scripts).
