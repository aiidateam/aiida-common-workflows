# -*- coding: utf-8 -*-
from aiida.engine import calcfunction, workfunction
from aiida.orm import Bool
from aiida_siesta.workflows.functions.protocols import ProtocolRegistry


class SiestaRelaxationInputsGenerator(ProtocolRegistry):
    """
    This class has two main purposes:
    1) Provide a method (get_builder) that returns a builder for the WorkChain
       SiestaBaseWorkChain with pre-compiled inputs according to a protocol and
       some relaxation options. This builder can be submitted to perform a Siesta
       relaxation.
    2) Implement few methods that can be used for the creation of a GUI that
       allow users to run a relaxation with Siesta after selecting options with
       few clicks. The GUI is meant to be common for every plugin that can perform a
       relaxation. Implementations of each code will be collected in the GitHub
       repository aiidateam/aiida-common-workflows.
    """

    _calc_types = {
        'relaxation': {
            'code_plugin': 'siesta.siesta',
            'description': 'These are calculations used for'
            'the main run of the code, computing the relaxation'
        }
    }
    _relax_types = {
        'atoms_only':
        'the latice shape and volume is fixed, only the athomic positions are relaxed',
        'variable_cell':
        'the lattice is relaxed together with the atomic coordinates. It allows'
        'to target hydro-static pressures or arbitrary stress tensors.',
        'constant_volume':
        'the cell volume is kept constant in a variable-cell relaxation: only'
        'the cell shape andthe atomic coordinates are allowed to change.  Note that'
        'it does not make much sense tospecify a target stress or pressure in this'
        'case, except for anisotropic (traceless) stresses'
    }

    @classmethod
    def get_calc_types(cls):
        return cls._calc_types.keys()

    @classmethod
    def get_calc_type_schema(cls, key):
        if key in cls._calc_types:
            return cls._calc_types[key]
        else:
            raise ValueError('Wrong calc_type: no calc_type {} implemented'.format(key))

    @classmethod
    def get_relaxation_types(cls):
        return cls._relax_types.keys()

    @classmethod
    def get_builder(
        cls, structure, calc_engines, protocol, relaxation_type, threshold_forces=None, threshold_stress=None
    ):

        from aiida_siesta.workflows.base import SiestaBaseWorkChain
        from aiida.orm import (Str, KpointsData, Dict, StructureData)
        from aiida.orm import load_code

        if protocol not in cls.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default standard'.format(protocol))
            protocol = cls.get_default_protocol_name()

        protocol_dict = cls.get_protocol(protocol)

        #K points
        kpoints_mesh = KpointsData()
        kpoints_mesh.set_cell_from_structure(structure)
        kp_dict = protocol_dict['kpoints']
        kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'], offset=kp_dict['offset'])

        #Parameters, including scf and relax options
        #scf
        parameters = protocol_dict['parameters'].copy()
        meshcutoff = 0
        min_meshcutoff = parameters['min_meshcut']  # In Rydberg (!)
        del parameters['min_meshcut']
        atomic_heuristics = protocol_dict['atomic_heuristics']
        for kind in structure.get_kind_names():
            try:
                cutoff = atomic_heuristics[kind]['cutoff']
                meshcutoff = max(meshcutoff, cutoff)
            except:
                pass  # No problem. No heuristics, no info
        meshcutoff = max(min_meshcutoff, meshcutoff)
        parameters['meshcutoff'] = str(meshcutoff) + ' Ry'
        #relaxation
        parameters['md-type-of-run'] = 'cg'
        parameters['md-num-cg-steps'] = 100
        if relaxation_type == 'variable_cell':
            parameters['md-variable-cell'] = True
        if relaxation_type == 'constant_volume':
            parameters['md-constant-volume'] = True
        if not threshold_forces:
            threshold_forces = protocol_dict['threshold_forces']
        if not threshold_stress:
            threshold_stress = protocol_dict['threshold_stress']
        parameters['md-max-force-tol'] = str(threshold_forces) + ' eV/Ang'
        parameters['md-max-stress-tol'] = str(threshold_stress) + ' eV/Ang**3'
        #Walltime equal to scheduler, prevents calc to be killed by scheduler (it is implemented
        #in WorkChain as well, but this generator is more general
        parameters['max-walltime'] = calc_engines['relaxation']['options']['max_wallclock_seconds']

        #Basis
        basis = protocol_dict['basis']

        #Pseudo fam
        cls.is_pseudofamily_loaded(protocol)
        pseudo_fam = protocol_dict['pseudo_family']

        builder = SiestaBaseWorkChain.get_builder()
        builder.structure = structure
        builder.basis = Dict(dict=basis)
        builder.parameters = Dict(dict=parameters)
        builder.kpoints = kpoints_mesh
        builder.pseudo_family = Str(pseudo_fam)
        builder.options = Dict(dict=calc_engines['relaxation']['options'])
        builder.code = code = load_code(calc_engines['relaxation']['code'])

        return builder
