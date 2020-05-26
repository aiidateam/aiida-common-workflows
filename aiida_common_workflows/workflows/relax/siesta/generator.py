# -*- coding: utf-8 -*-
import yaml
from aiida_common_workflows.workflows.relax.generator import RelaxInputsGenerator, RelaxType
from aiida_common_workflows.workflows.relax.siesta.workchain import SiestaRelaxWorkChain
import os

__all__ = ('SiestaRelaxInputsGenerator',)


class SiestaRelaxInputsGenerator(RelaxInputsGenerator):

    _default_protocol = 'standard_delta'

    filepath = os.path.join(os.path.dirname(__file__), 'protocols_registry.yaml')

    with open(filepath) as thefile:
        _protocols = yaml.full_load(thefile)

    _calc_types = {
        'relaxation': {
            'code_plugin': 'siesta.siesta',
            'description': 'These are calculations used for'
            'the main run of the code, computing the relaxation'
        }
    }
    _relax_types = {
        RelaxType.ATOMS:
        'the latice shape and volume is fixed, only the athomic positions are relaxed',
        RelaxType.ATOMS_CELL:
        'the lattice is relaxed together with the atomic coordinates. It allows'
        'to target hydro-static pressures or arbitrary stress tensors.',
        #    'constant_volume':'the cell volume is kept constant in a variable-cell relaxation: only'
        #        'the cell shape and the atomic coordinates are allowed to change.  Note that'
        #        'it does not make much sense to specify a target stress or pressure in this'
        #        'case, except for anisotropic (traceless) stresses'
    }

    # pylint: disable=too-many-locals
    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        **kwargs
    ):

        from aiida.orm import (Str, KpointsData, Dict)
        from aiida.orm import load_code

        #Checks
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default standard'.format(protocol))
            protocol = self.get_default_protocol_name()
        if relaxation_type not in self.get_relaxation_types():
            raise ValueError('Wrong relaxation type: no relax_type with name {} implemented'.format(relaxation_type))

        #Initialization
        protocol_dict = self.get_protocol(protocol)
        atomic_heuristics = protocol_dict['atomic_heuristics']

        #K points
        kpoints_mesh = KpointsData()
        kpoints_mesh.set_cell_from_structure(structure)
        kp_dict = protocol_dict['kpoints']
        kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'], offset=kp_dict['offset'])

        #Parameters, including scf and relax options
        #scf
        parameters = protocol_dict['parameters'].copy()
        #meshcutoff = 0
        min_meshcutoff = parameters['min_meshcut']  # In Rydberg (!)
        del parameters['min_meshcut']
        #Part of atom-dependent mesh cut need to be discussed
        #for kind in structure.get_kind_names():
        #    if atomic_heuristics[kind]:
        #        cutoff = atomic_heuristics[kind]['cutoff']
        #        meshcutoff = max(meshcutoff, cutoff)
        #meshcutoff = max(min_meshcutoff, meshcutoff)
        #parameters["meshcutoff"] = str(meshcutoff) + " Ry"
        parameters['meshcutoff'] = str(min_meshcutoff) + ' Ry'
        #relaxation
        parameters['md-type-of-run'] = 'cg'
        parameters['md-num-cg-steps'] = 100
        if relaxation_type == 'variable_cell':
            parameters['md-variable-cell'] = True
        if relaxation_type == 'constant_volume':
            parameters['md-variable-cell'] = True
            parameters['md-constant-volume'] = True
        if not threshold_forces:
            threshold_forces = protocol_dict['threshold_forces']
        if not threshold_stress:
            threshold_stress = protocol_dict['threshold_stress']
        parameters['md-max-force-tol'] = str(threshold_forces) + ' eV/Ang'
        parameters['md-max-stress-tol'] = str(threshold_stress) + ' eV/Ang**3'

        #Basis
        basis = protocol_dict['basis']
        for kind in structure.get_kind_names():
            try:
                cust_basis = atomic_heuristics[kind]['basis']
                if 'split-norm' in cust_basis:
                    basis['PaoSplitTailNorm'] = True
                if 'polarization' in cust_basis:
                    basis['%block PaoPolarizationScheme'
                          ] = '\n {} non-perturbative\n%endblock PaoPolarizationScheme'.format(kind)
            except KeyError:
                pass

        #Pseudo fam
        pseudo_fam = protocol_dict['pseudo_family']

        builder = SiestaRelaxWorkChain.get_builder()
        builder.structure = structure
        builder.basis = Dict(dict=basis)
        builder.parameters = Dict(dict=parameters)
        builder.kpoints = kpoints_mesh
        builder.pseudo_family = Str(pseudo_fam)
        builder.options = Dict(dict=calc_engines['relaxation']['options'])
        builder.code = load_code(calc_engines['relaxation']['code'])

        return builder
