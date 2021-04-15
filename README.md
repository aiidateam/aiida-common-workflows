# `aiida-common-workflows`
The AiiDA common workflows project provides computational workflows, implemented in [AiiDA](https://www.aiida.net), to compute various material properties using any of the quantum engines that implement it.
The distinguishing feature is that the interfaces of the AiiDA common workflows are uniform, independent of the quantum engine that is used underneath to perform the material property simulations.
These common interfaces make it trivial to switch from quantum engine.
In addition to the common interface, the workflows provide input generators that automatically define the required inputs for a given task and desired computational precision.
For more information, please refer to the [online documentation](https://aiida-common-workflows.readthedocs.io/en/latest/).


## How to cite
If you use the workflow of this package, please cite the [original paper (doi:)]().
In addition, one should cite the quantum engines whose implementations are used.

Engine           | DOIs or URLs to be cited
---------------- | ----------------------------
ABINIT           | [10.1016/j.cpc.2016.04.003](https://doi.org/10.1016/j.cpc.2016.04.003) [10.1016/j.cpc.2019.107042](https://doi.org/10.1016/j.cpc.2019.107042) [10.1063/1.5144261](https://doi.org/10.1063/1.5144261)
BigDFT           | [10.1063/5.0004792](https://doi.org/10.1063/5.0004792)
CASTEP           | [10.1524/zkri.220.5.567.65075](https://doi.org/10.1524/zkri.220.5.567.65075)
CP2K             | [10.1002/wcms.1159](https://doi.org/10.1002/wcms.1159) [10.1063/5.0007045](https://doi.org/10.1063/5.0007045)
FLEUR            | [https://www.flapw.de](https://www.flapw.de)
Gaussian         |
NWChem           | [10.1063/5.0004997](https://doi.org/10.1063/5.0004997)
ORCA             | [10.1002/wcms.81](https://doi.org/10.1002/wcms.81) [10.1002/wcms.1327](https://doi.org/10.1002/wcms.1327)
Quantum ESPRESSO | [10.1088/0953-8984/21/39/395502](https://doi.org/10.1088/0953-8984/21/39/395502) [10.1088/1361-648x/aa8f79](https://doi.org/10.1088/1361-648x/aa8f79)
SIESTA           | [10.1063/5.0005077](https://doi.org/10.1063/5.0005077) [10.1088/0953-8984/14/11/302](https://doi.org/10.1088/0953-8984/14/11/302)
VASP             | [10.1103/physrevb.54.11169](https://doi.org/10.1103/physrevb.54.11169)  [10.1103/physrevb.59.1758](https://doi.org/10.1103/physrevb.59.1758)
