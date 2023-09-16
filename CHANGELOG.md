# Change log

## 1.0.1 - 2023-09-16

### Fixes

- Use consistent capitalization in name of `verification-PBE-v1` protocol: PBE should be capitalized [[f4da766]](https://github.com/aiidateam/aiida-common-workflows/commit/f4da766aa34570aef7b60cb488c07bd013a2afc6)


## 1.0.0 - 2023-09-10

This is the first stable release of the package.
It is compatible with AiiDA v1.6 and supports Python 3.8 and 3.9.
This release adds the `verification-PBE-v1` protocol for the `CommonRelaxWorkChain` as described and used in the study entitled ["How to verify the precision of density-functional-theory implementations via reproducible and universal workflows"](https://arxiv.org/abs/2305.17274).
The abinit, BigDFT, CASTEP, CP2K, Fleur, Quantum ESPRESSO, SIESTA and VASP codes, which had an existing implementation of the `CommonRelaxWorkChain`, added support for this protocol.
A brand new implementation of the `CommonRelaxWorkChain` is added for the [GPAW](https://wiki.fysik.dtu.dk/gpaw/) and [WIEN2k](http://susi.theochem.tuwien.ac.at/) codes.

### Features
- `CommonRelaxWorkChain` : Add implementation for GPAW [[fa9c92c]](https://github.com/aiidateam/aiida-common-workflows/commit/fa9c92ce63476ccf91ffe38e5926aaf05f6b64d9)
- `CommonRelaxWorkChain` : Add implementation for WIEN2k [[3e4014d]](https://github.com/aiidateam/aiida-common-workflows/commit/3e4014d8b38ca944e61d67f29523df37165548b8)
- Add the `CommonBandsWorkChain` [[aacaca0]](https://github.com/aiidateam/aiida-common-workflows/commit/aacaca00811461ca3c07ea318b7dd26f514178f3)
- Add the `verification-PBE-v1` protocol for abinit [[c762164]](https://github.com/aiidateam/aiida-common-workflows/commit/c762164b4b4b51f233a91a60dac1d48334406749)
- Add the `verification-PBE-v1` protocol for BigDFT  [[34ef55f]](https://github.com/aiidateam/aiida-common-workflows/commit/34ef55fea714f6a05ff6b4bdd1b043f29fa3c958)
- Add the `verification-PBE-v1` protocol for CASTEP [[db0f1ae]](https://github.com/aiidateam/aiida-common-workflows/commit/db0f1ae125e045183f69cd42d09f58fd69c2bff8)
- Add the `verification-PBE-v1` protocol for CP2K [[7d7cc9f]](https://github.com/aiidateam/aiida-common-workflows/commit/7d7cc9f619e262479a324adea48575c29db53619)
- Add the `verification-PBE-v1` protocol for Fleur [[ac214b1]](https://github.com/aiidateam/aiida-common-workflows/commit/ac214b127686f330aec05d164bf6e68270ef0ca9)
- Add the `verification-PBE-v1` protocol for Quantum ESPRESSO [[021672a]](https://github.com/aiidateam/aiida-common-workflows/commit/021672a4dd38934d30b62a8fa6d31a379719856f)
- Add the `verification-PBE-v1` protocol for SIESTA [[1aa93c4]](https://github.com/aiidateam/aiida-common-workflows/commit/1aa93c4853bd9b64abb7e627b60b5780c3c79a4b)
- Add the `verification-PBE-v1` protocol for VASP [[a17cd87]](https://github.com/aiidateam/aiida-common-workflows/commit/a17cd871c4ef9a85eb50ec6ae5a231cfa95b522a)
- Add the `verification-PBE-v1-sirius` protocol for CP2K [[3015631]](https://github.com/aiidateam/aiida-common-workflows/commit/30156316c440f5e9843accb8590d1c34b2ed15f7)
- CLI: Add option to define threads (cores-per-mpiproc) [[f838218]](https://github.com/aiidateam/aiida-common-workflows/commit/f83821898d1746a871373d538d8133f0efd22c1d)
- CLI: Call `sys.exit` for launch command if process fails [[bb9090a]](https://github.com/aiidateam/aiida-common-workflows/commit/bb9090a8bd8bc703ffaeda42b439dcfeebf55bf5)
- CLI: Add entry point for CLI as `acwf` [[611c2e6]](https://github.com/aiidateam/aiida-common-workflows/commit/611c2e6ce11c6e9705e3a66e4a43a9e574dc1dd1)
- CLI: Add `--engine-options` parameter to specify calcjob options [[a024f47]](https://github.com/aiidateam/aiida-common-workflows/commit/a024f472e27c88e8c59cdc323f39f0b415cdd077)
- Docs: Add a Sphinx extension to auto document input generators [[03556c6]](https://github.com/aiidateam/aiida-common-workflows/commit/03556c6a52e467195f789f311b379b6d57e306de)
- Add new `UNKNOWN` type to `ElectronicType` [[3bf3ffb]](https://github.com/aiidateam/aiida-common-workflows/commit/3bf3ffb8601dcc8b21abc4280336181236014654)
- Add the `get_ts_energy` function for Quantum ESPRESSO [[f1e1a37]](https://github.com/aiidateam/aiida-common-workflows/commit/f1e1a376a4047b491e40c02c1adcca79be86609f)
- Implement the concept of input generator specifications [[cd82fd9]](https://github.com/aiidateam/aiida-common-workflows/commit/cd82fd9b2aa445aaf1afe08e5e6ea049b6be7a6a)

### Fixes
- CLI: Fix the units of the dissociation curve plot [[a1c64a9]](https://github.com/aiidateam/aiida-common-workflows/commit/a1c64a94bfd1d253ff270b698a6a2159c9a5d6a6)
- `EquationOfStateWorkChain`: Fix bug in `get_scale_factors` [[2042324]](https://github.com/aiidateam/aiida-common-workflows/commit/2042324cbac9f45765c993cb7851fb3fe460508a)
- `EquationOfStateWorkChain`: Fix `reference_workchain` use [[fc74f25]](https://github.com/aiidateam/aiida-common-workflows/commit/fc74f2572fe22eb42fac2d94d157a72d8d8d1ca7)
- `QuantumEspressoCommonRelaxWorkChain`: Fix stress units [[ad3761e]](https://github.com/aiidateam/aiida-common-workflows/commit/ad3761eb41474bbbf413ed1d948231d03762a3c2)
- `QuantumEspressoCommonRelaxWorkChain`: Apply `options` to `base_final_scf` namespace [[9aab4d0]](https://github.com/aiidateam/aiida-common-workflows/commit/9aab4d0f8ca0ed294d08393c4f75f1334f50f274)
- `get_builder`: Do not deep-copy nodes [[facf481]](https://github.com/aiidateam/aiida-common-workflows/commit/facf481944a507363708935f7eb79a3bb6c95fe6)
- Abinit protocol and generator tweaks [[45380d9]](https://github.com/aiidateam/aiida-common-workflows/commit/45380d9b295fdfdfea4138d0fec603f2b2162efe)

### Dependencies
- Drop support for Python 3.7 [[ae9cb90]](https://github.com/aiidateam/aiida-common-workflows/commit/ae9cb905f5500ae76716173f25644e0e16822d6c)
- Add upper limit `numpy<1.24.0` [[51c289a]](https://github.com/aiidateam/aiida-common-workflows/commit/51c289af1e0ebbcf504606faeff591c530211f40)
- Pin `abipy` version [[4023b61]](https://github.com/aiidateam/aiida-common-workflows/commit/4023b61486c8cbd0786d2479dece8a463e890292)
- Unpin `ase` but do not allow `ase==3.20` which is broken [[0d9cf51]](https://github.com/aiidateam/aiida-common-workflows/commit/0d9cf519c5e572f2a243d4c5b436ae3e7e52b6e2)
- Pin version of aiida-pseudo to 0.6.5 [[da95798]](https://github.com/aiidateam/aiida-common-workflows/commit/da957982d9074bb79288d6a633fa49cad3541f88)

### Devops
- Add common tests for input generators of common relax workflow [[f83cbba]](https://github.com/aiidateam/aiida-common-workflows/commit/f83cbba9035d0f794f3ba9261179e52c91008aa1)
- Adopt PEP 621 and move build spec to `pyproject.toml` [[9a28526]](https://github.com/aiidateam/aiida-common-workflows/commit/9a28526653ced05dc61b8f45ccd3069cda9c6e77)
- Add continuous deployment workflow [[662b0e1]](https://github.com/aiidateam/aiida-common-workflows/commit/662b0e1bd35c7545b7b2126280dd4c8bf7266dd2)
- Fix the CI workflow [[eaeb979]](https://github.com/aiidateam/aiida-common-workflows/commit/eaeb979e9561506502285a062cbbe1b8f8d2a567)


## 0.1.0 - 2021-04-28

First release
