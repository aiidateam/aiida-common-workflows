# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for BigDFT."""
from typing import Any, Dict, List

from aiida import engine
from aiida import orm
from aiida import plugins

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('BigDftRelaxInputsGenerator',)

BigDFTParameters = plugins.DataFactory('bigdft')
StructureData = plugins.DataFactory('structure')


def ortho_struct(input):
    # Create and update a dict to pass to transform_to_orthorombic,
    # and then get back data to the input dict
    dico = dict()
    dico["name"] = input.sites[0].kind_name
    dico["a"] = round(input.cell_lengths[0], 6)
    dico["alpha"] = round(input.cell_angles[0], 6)
    dico["b"] = round(input.cell_lengths[1], 6)
    dico["beta"] = round(input.cell_angles[1], 6)
    dico["c"] = round(input.cell_lengths[2], 6)
    dico["gamma"] = round(input.cell_angles[2], 6)
    dico["nat"] = nat = len(input.sites)
    # use abc coordinates
    for i in range(dico["nat"]):
        dico[i + 1] = list(input.get_pymatgen().sites[i].frac_coords)
    BigDFTParameters.transform_to_orthorombic(dico)
    output = input.clone()
    output.clear_sites()
    output.cell = [[dico["a"], 0, 0], [0, dico["b"], 0], [0, 0, dico["c"]]]
    for i in range(dico["nat"]):
        site = input.sites[0]
        site.position = (dico[i + 1][0] * dico["a"],
                         dico[i + 1][1] * dico["b"],
                         dico[i + 1][2] * dico["c"])
        output.append_site(site)
    return output, dico


class BigDftRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `BigDFTRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'This profile should be chosen if speed is more important than accuracy.',
            'inputdict_cubic': {
                'dft': {
                    'hgrids': 0.45
                }
            },
            'inputdic_linear': {
                'import': 'linear_fast'
            },
            'kpoints_distance': 100

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
                    'hgrids': 0.15
                }
            },
            'inputdict_linear': {
                'import': 'linear_accurate'
            },
            'kpoints_distance': 20

        }
    }

    _calc_types = {'relax': {'code_plugin': 'bigdft',
                             'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
    }
    _spin_types = {SpinType.NONE: 'nspin : 1',
                   SpinType.COLLINEAR: 'nspin: 2'}
    _electronic_types = {ElectronicType.METAL: 'using specific mixing inputs', 
                         ElectronicType.INSULATOR: 'using default mixing inputs'}

    def get_builder(
        self,
        structure: StructureData,
        calc_engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        previous_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param calc_engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param previous_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            calc_engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            previous_workchain=previous_workchain,
            **kwargs
        )

        from aiida.orm import Dict, Float, Bool
        from aiida.orm import load_code
        import pymatgen

        if relax_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        else:
            raise ValueError(
                'relaxation type `{}` is not supported'.format(relax_type.value))

        builder = self.process_class.get_builder()

        pymatgen_struct = structure.get_pymatgen()
        ortho_dict = None
        # for single atom computations, we should actually not perform relaxation
        if (pymatgen_struct.ntypesp <= 1):
            builder.relax.perform = orm.Bool(False)
            # pass the structure through a transform to generate orthorhombic structure if possible/needed.
            newstruct, ortho_dict = ortho_struct(structure)
            newstruct.store()
            builder.structure = newstruct
        else:
            builder.structure = structure

        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        import copy
        if len(builder.structure.sites) <= 200:
            inputdict = copy.deepcopy(
                self.get_protocol(protocol)['inputdict_cubic'])
        else:
            inputdict = copy.deepcopy(
                self.get_protocol(protocol)['inputdict_linear'])

        # adapt hgrid to the strain
        if previous_workchain is not None and previous_workchain.is_finished_ok:
            logfile = previous_workchain.outputs.bigdft_logfile.logfile
            if(isinstance(logfile, list)):
                hgrids = logfile[0].get('dft').get('hgrids')
            else:
                hgrids = logfile.get('dft').get('hgrids')
            inputdict["dft"]["hgrids"] = hgrids[0] * builder.structure.cell_lengths[0] / \
                previous_workchain.inputs.structure.cell_lengths[0]

#       TODO : Use inputActions
        if electronic_type is ElectronicType.METAL:
            if 'mix' not in inputdict:
                inputdict['mix'] = {}
            inputdict['mix'].update({'iscf': 17, 'itrpmax': 200, 'rpnrm_cv': 1.E-12,
                                    'norbsempty': 120, 'tel': 0.01, 'alphamix': 0.8, 'alphadiis': 1.0})
        if spin_type is SpinType.NONE:
            inputdict['dft'].update({'nspin': 1})
        elif spin_type is SpinType.COLLINEAR:
            inputdict['dft'].update({'nspin': 2})

        if ortho_dict is not None:
            inputdict = BigDFTParameters.set_inputfile(
                inputdict["dft"]["hgrids"], ortho_dict, inputdict, units="angstroem")
        else:
            inputdict["kpt"] = BigDFTParameters.set_kpoints(
                len(builder.structure.sites))
            if (pymatgen_struct.ntypesp <= 1):
                inputdict["dft"].update(
                    BigDFTParameters.set_spin(
                        builder.structure.sites[0].kind_name,
                        len(builder.structure.sites)
                    )
                )

        if magnetization_per_site:
            for (i, at) in enumerate(inputdict["posinp"]["positions"]):
                at["IGSpin"] = int(magnetization_per_site[i])

        builder.parameters = BigDFTParameters(dict=inputdict)
        builder.code = orm.load_code(calc_engines[relaxation_schema]['code'])
        run_opts = {'options': calc_engines[relaxation_schema]['options']}
        builder.run_opts = orm.Dict(dict=run_opts)

        if threshold_forces is not None:
            builder.relax.threshold_forces = orm.Float(threshold_forces)

        return builder
