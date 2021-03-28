# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for BigDFT."""
from typing import Any, Dict, List

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.engine import calcfunction

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('BigDftCommonRelaxInputGenerator',)

BigDFTParameters = plugins.DataFactory('bigdft')
StructureData = plugins.DataFactory('structure')


@calcfunction
def ortho_struct(input_struct):
    """Create and update a dict to pass to transform_to_orthorombic,
      and then get back data to the input dict """
    dico = dict()
    dico['name'] = input_struct.sites[0].kind_name
    dico['a'] = round(input_struct.cell_lengths[0], 6)
    dico['alpha'] = round(input_struct.cell_angles[0], 6)
    dico['b'] = round(input_struct.cell_lengths[1], 6)
    dico['beta'] = round(input_struct.cell_angles[1], 6)
    dico['c'] = round(input_struct.cell_lengths[2], 6)
    dico['gamma'] = round(input_struct.cell_angles[2], 6)
    dico['nat'] = len(input_struct.sites)
    # use abc coordinates
    import pymatgen
    periodic = 0
    for i in range(dico['nat']):
        site = input_struct.get_pymatgen().sites[i]
        if isinstance(site, pymatgen.core.sites.PeriodicSite):
            periodic = 1
            dico[str(i + 1)] = list(site.frac_coords)
        else:
            dico[str(i + 1)] = (site.coords[0] / dico['a'], site.coords[1] / dico['b'], site.coords[2] / dico['c'])
    BigDFTParameters.transform_to_orthorombic(dico)
    output = input_struct.clone()
    output.clear_sites()
    output.cell = [[dico['a'], 0, 0], [0, dico['b'], 0], [0, 0, dico['c']]]
    for i in range(dico['nat']):
        site = input_struct.sites[0]
        if periodic == 1:
            site.position = (
                dico[str(i + 1)][0] * dico['a'], dico[str(i + 1)][1] * dico['b'], dico[str(i + 1)][2] * dico['c']
            )
        else:
            site.position = dico[str(i + 1)]
        output.append_site(site)
    out = {'outstruct': output, 'outdict': dico}
    return out


class BigDftCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `BigDftCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'This profile should be chosen if speed is more important than accuracy.',
            'inputdict_cubic': {
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-7,
                    'hgrids': 0.45
                },
                'mix': {
                    'iscf': 7,
                    'itrpmax': 200,
                    'rpnrm_cv': 1e-10,
                    'tel': 1e-3,
                    'alphamix': 0.5,
                    'norbsempty': 1000,
                    'alphadiis': 1.0
                }
            },
            'inputdic_linear': {
                'import': 'linear_fast'
            },
            'kpoints_distance': 20
        },
        'moderate': {
            'description': 'This profile should be chosen if accurate forces are required, but there is no need for '
            'extremely accurate energies.',
            'inputdict_cubic': {
                'logfile': 'Yes',
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.3
                },
                'mix': {
                    'iscf': 7,
                    'itrpmax': 200,
                    'rpnrm_cv': 1e-12,
                    'tel': 1e-3,
                    'alphamix': 0.5,
                    'norbsempty': 1000,
                    'alphadiis': 1.0
                }
            },
            'inputdict_linear': {
                'import': 'linear'
            },
            'kpoints_distance': 40
        },
        'precise': {
            'description': 'This profile should be chosen if highly accurate energy differences are required.',
            'inputdict_cubic': {
                'dft': {
                    'ixc': 'PBE',
                    'ncong': 2,
                    'rmult': [10, 8],
                    'itermax': 3,
                    'idsx': 0,
                    'gnrm_cv': 1e-8,
                    'hgrids': 0.15
                },
                'mix': {
                    'iscf': 7,
                    'itrpmax': 200,
                    'rpnrm_cv': 1e-12,
                    'tel': 1e-3,
                    'alphamix': 0.5,
                    'norbsempty': 1000,
                    'alphadiis': 1.0
                }
            },
            'inputdict_linear': {
                'import': 'linear_accurate'
            },
        }
    }

    _engine_types = {'relax': {'code_plugin': 'bigdft', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.NONE: 'No relaxation'
    }
    _spin_types = {SpinType.NONE: 'nspin : 1', SpinType.COLLINEAR: 'nspin: 2'}
    _electronic_types = {
        ElectronicType.METAL: 'using specific mixing inputs',
        ElectronicType.INSULATOR: 'using default mixing inputs'
    }

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.POSITIONS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            reference_workchain=reference_workchain,
            **kwargs
        )

        builder = self.process_class.get_builder()

        if relax_type == RelaxType.POSITIONS:
            relaxation_schema = 'relax'
        elif relax_type == RelaxType.NONE:
            relaxation_schema = 'relax'
            builder.relax.perform = orm.Bool(False)
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        pymatgen_struct = structure.get_pymatgen()
        ortho_dict = None
        if pymatgen_struct.ntypesp <= 1:
            # pass the structure through a transform to generate orthorhombic structure if possible/needed.
            new = ortho_struct(structure)
            newstruct = new.get('outstruct')
            ortho_dict = new.get('outdict')
            newstruct.store()
            builder.structure = newstruct
        else:
            builder.structure = structure

        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        import copy
        if len(builder.structure.sites) <= 200:
            inputdict = copy.deepcopy(self.get_protocol(protocol)['inputdict_cubic'])
        else:
            inputdict = copy.deepcopy(self.get_protocol(protocol)['inputdict_linear'])

        # adapt hgrid to the strain
        if reference_workchain is not None and reference_workchain.is_finished_ok:
            logfile = reference_workchain.outputs.bigdft_logfile.logfile
            if isinstance(logfile, list):
                hgrids = logfile[0].get('dft').get('hgrids')
            else:
                hgrids = logfile.get('dft').get('hgrids')
            inputdict['dft']['hgrids'] = hgrids[0] * builder.structure.cell_lengths[0] / \
                reference_workchain.inputs.structure.cell_lengths[0]


#       Soon : Use inputActions
        if electronic_type is ElectronicType.METAL:
            if 'mix' not in inputdict:
                inputdict['mix'] = {}
            inputdict['mix'].update({
                'iscf': 17,
                'itrpmax': 200,
                'rpnrm_cv': 1.E-12,
                'norbsempty': 120,
                'tel': 0.01,
                'alphamix': 0.8,
                'alphadiis': 1.0
            })
        if spin_type is SpinType.NONE:
            inputdict['dft'].update({'nspin': 1})
        elif spin_type is SpinType.COLLINEAR:
            inputdict['dft'].update({'nspin': 2})
        psp = []
        if ortho_dict is not None:
            inputdict = BigDFTParameters.set_inputfile(
                inputdict['dft']['hgrids'], ortho_dict, inputdict, psp=psp, units='angstroem'
            )
        else:
            # use HGH pseudopotentials instead of default ones from BigDFT, if the user does not specify new ones.
            # This may be moved to the plugin if we decide to make it the default behavior.
            for elem in pymatgen_struct.types_of_specie:
                BigDFTParameters.set_psp(elem.name, psp)
            inputdict['kpt'] = BigDFTParameters.set_kpoints(len(builder.structure.sites))
            if pymatgen_struct.ntypesp <= 1:
                inputdict['dft'].update(
                    BigDFTParameters.set_spin(builder.structure.sites[0].kind_name, len(builder.structure.sites))
                )
        if magnetization_per_site:
            for (i, atom) in enumerate(inputdict['posinp']['positions']):
                atom['IGSpin'] = int(magnetization_per_site[i])
        # correctly set kpoints from protocol fast and moderate. If precise, use the ones from set_inputfile/set_kpt
        if self.get_protocol(protocol).get('kpoints_distance'):
            inputdict['kpt'] = {'method': 'auto', 'kptrlen': self.get_protocol(protocol).get('kpoints_distance')}
        if psp:
            import os
            builder.pseudos = orm.List()
            psprel = [os.path.normpath(os.path.relpath(i)) for i in psp]
            builder.pseudos.extend(psprel)
        builder.parameters = BigDFTParameters(dict=inputdict)
        builder.code = orm.load_code(engines[relaxation_schema]['code'])
        run_opts = {'options': engines[relaxation_schema]['options']}
        builder.run_opts = orm.Dict(dict=run_opts)

        if threshold_forces is not None:
            builder.relax.threshold_forces = orm.Float(threshold_forces)

        return builder
