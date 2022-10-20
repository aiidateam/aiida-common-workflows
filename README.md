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
NWChem           | [10.1063/5.0004997](https://doi.org/10.1063/5.0004997)
ORCA             | [10.1002/wcms.81](https://doi.org/10.1002/wcms.81) [10.1002/wcms.1327](https://doi.org/10.1002/wcms.1327)
Quantum ESPRESSO | [10.1088/0953-8984/21/39/395502](https://doi.org/10.1088/0953-8984/21/39/395502) [10.1088/1361-648x/aa8f79](https://doi.org/10.1088/1361-648x/aa8f79)
SIESTA           | [10.1063/5.0005077](https://doi.org/10.1063/5.0005077) [10.1088/0953-8984/14/11/302](https://doi.org/10.1088/0953-8984/14/11/302)
VASP             | [10.1103/physrevb.54.11169](https://doi.org/10.1103/physrevb.54.11169)  [10.1103/physrevb.59.1758](https://doi.org/10.1103/physrevb.59.1758)

## Team

The common workflows project is the result of a large international collaboration of developers and researchers:

_Emanuele Bosoni(1), Louis Beal(2), Marnik Bercx(3), Peter Blaha(4), Stefan Blügel(5), Jens Bröder(5), Martin Callsen(6,7), Stefaan Cottenier(6), Augustin Degomme(2), Vladimir Dikan(1), Kristjan Eimre (3), Espen Flage-Larsen(8,9), Marco Fornari (26), Alberto Garcia(1), Luigi Genovese(2), Matteo Giantomassi(10), Sebastiaan P. Huber(3), Henning Janssen(5), Georg Kastlunger(11), Matthias Krack(12), Thomas D. Kühne(13), Kurt Lejaeghere(6,14), Georg K. H. Madsen(4), Nicola Marzari(3,12), Gregor Michalicek(5), Hossein Mirhosseini(13), Tiziano M. A. Müller(15), Guido Petretto(10), Chris J. Pickard(16,17), Samuel Poncé(10), Gian-Marco Rignanese(10), Oleg Rubel(18), Thomas Ruh(4,6), Michael Sluydts(6,19), Danny E. P. Vanpoucke(6,20), Sudarshan Vijay(11), Michael Wolloch(21,22), Daniel Wortmann(5), Aliaksandr V. Yakutovich(23), Jusong Yu (3), Austin Zadoks(3), Bonan Zhu(24,25), Giovanni Pizzi(3)_

Affiliations:

1) ICMAB-CSIC, Spain
2) Univ. Grenoble-Alpes, CEA, France
3) EPFL, Switzerland
4) Technical University of Vienna, Austria
5) Forschungszentrum Jülich, Germany
6) Ghent University, Belgium
7) Academia Sinica, Taiwan
8) SINTEF Industry, Norway
9) University of Oslo, Norway
10) Université catholique de Louvain, Belgium
11) DTU, Denmark
12) PSI, Switzerland
13) University of Paderborn, Germany
14) OCAS NV/ArcelorMittal Global R&D, Belgium
15) HPE HPC/AI Research Lab, Switzerland
16) University of Cambridge, United Kingdom
17) Tohoku University, Japan
18) McMaster University, Canada
19) ePotentia, Belgium
20) Hasselt University, Belgium
21) University of Vienna, Austria
22) VASP Software GmbH, Austria
23) Empa, Switzerland
24) University College London, United Kingdom
25) The Faraday Institution, United Kingdom
26) Central Michigan University, USA
