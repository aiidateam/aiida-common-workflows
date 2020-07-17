# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for SIESTA."""
import os
import yaml
from aiida.common import exceptions
from aiida.orm import Group
from aiida_common_workflows.workflows.relax.generator import RelaxInputsGenerator, RelaxType

__all__ = ('SiestaRelaxInputsGenerator',)


class SiestaRelaxInputsGenerator(RelaxInputsGenerator):
    """Generator of inputs for the SiestaRelaxWorkChain"""

    _default_protocol = 'moderate'

    _calc_types = {
        'relaxation': {
            'code_plugin':
            'siesta.siesta',
            'description':
            'These are calculations used for the main and '
            'only run of the code, computing the relaxation, in calc_engines the user must '
            'define a code and options compatibles with plugin siesta.siesta'
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

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError('invalid protocol registry `{}`: '.format(self.__class__.__name__) + message)

        for k, v in self._protocols.items():  # pylint: disable=invalid-name

            if 'parameters' not in v:
                raise_invalid('protocol `{}` does not define the mandatory key `parameters`'.format(k))
            if 'mesh-cutoff' in v['parameters']:
                try:
                    float(v['parameters']['mesh-cutoff'].split()[0])
                    str(v['parameters']['mesh-cutoff'].split()[1])
                except (ValueError, IndexError):
                    raise_invalid(
                        'Wrong format of `mesh-cutoff` in `parameters` of protocol '
                        '`{}`. Value and units are required'.format(k)
                    )

            if 'basis' not in v:
                raise_invalid('protocol `{}` does not define the mandatory key `basis`'.format(k))

            if 'pseudo_family' not in v:
                raise_invalid('protocol `{}` does not define the mandatory key `pseudo_family`'.format(k))

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        _filepath = os.path.join(os.path.dirname(__file__), 'protocols_registry.yaml')

        with open(_filepath) as _thefile:
            self._protocols = yaml.full_load(_thefile)

    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        **kwargs
    ):  # pylint: disable=too-many-locals

        from aiida.orm import Dict
        from aiida.orm import load_code

        # Checks
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        if relaxation_type not in self.get_relaxation_types():
            raise ValueError('Wrong relaxation type: no relax_type with name {} implemented'.format(relaxation_type))
        if 'relaxation' not in calc_engines:
            raise ValueError('The `calc_engines` dictionaly must contain "relaxation" as outermost key')

        pseudo_family = self._protocols[protocol]['pseudo_family']
        try:
            Group.objects.get(label=pseudo_family)
        except exceptions.NotExistent:
            raise ValueError(
                'protocol `{}` requires `pseudo_family` with name {} '
                'but no family with this name is loaded in the database'.format(protocol, pseudo_family)
            )

        # K points
        kpoints_mesh = self._get_kpoints(protocol, structure)

        # Parameters, including scf and relax options
        parameters = self._get_param(protocol, structure)
        parameters['md-type-of-run'] = 'cg'
        parameters['md-num-cg-steps'] = 100
        if relaxation_type == RelaxType.ATOMS_CELL:
            parameters['md-variable-cell'] = True
        # if relaxation_type == 'constant_volume':
        #     parameters['md-variable-cell'] = True
        #     parameters['md-constant-volume'] = True
        if threshold_forces:
            parameters['md-max-force-tol'] = str(threshold_forces) + ' eV/Ang'
        if threshold_stress:
            parameters['md-max-stress-tol'] = str(threshold_stress) + ' eV/Ang**3'

        # Basis
        basis = self._get_basis(protocol, structure)

        # Pseudo fam
        pseudo_family = self._get_pseudo_fam(protocol)

        builder = self.process_class.get_builder()
        builder.structure = structure
        builder.basis = Dict(dict=basis)
        builder.parameters = Dict(dict=parameters)
        if kpoints_mesh:
            builder.kpoints = kpoints_mesh
        builder.pseudo_family = pseudo_family
        builder.options = Dict(dict=calc_engines['relaxation']['options'])
        builder.code = load_code(calc_engines['relaxation']['code'])

        return builder

    def _get_param(self, key, structure):  # pylint: disable=too-many-branches
        """
        Method to construct the `parameters` input. Heuristics are applied, a dictionary
        with the parameters is returned.
        """
        parameters = self._protocols[key]['parameters'].copy()

        if 'atomic_heuristics' in self._protocols[key]:  # pylint: disable=too-many-nested-blocks
            atomic_heuristics = self._protocols[key]['atomic_heuristics']

            if 'mesh-cutoff' in parameters:
                meshcut_glob = parameters['mesh-cutoff'].split()[0]
                meshcut_units = parameters['mesh-cutoff'].split()[1]
            else:
                meshcut_glob = None

            # Run through heuristics
            for kind in structure.kinds:
                need_to_apply = False
                try:
                    cust_param = atomic_heuristics[kind.symbol]['parameters']
                    need_to_apply = True
                except KeyError:
                    pass
                if need_to_apply:
                    if 'mesh-cutoff' in cust_param:
                        try:
                            cust_meshcut = float(cust_param['mesh-cutoff'].split()[0])
                        except (ValueError, IndexError):
                            raise RuntimeError(
                                'Wrong `mesh-cutoff` value for heuristc '
                                '{0} of protocol {1}'.format(kind.symbol, key)
                            )
                        if meshcut_glob:
                            if cust_meshcut > float(meshcut_glob):
                                meshcut_glob = cust_meshcut
                        else:
                            meshcut_glob = cust_meshcut
                            try:
                                meshcut_units = cust_param['mesh-cutoff'].split()[1]
                            except (ValueError, IndexError):
                                raise RuntimeError(
                                    'Wrong `mesh-cutoff` units for heuristc '
                                    '{0} of protocol {1}'.format(kind.symbol, key)
                                )

            if meshcut_glob:
                parameters['mesh-cutoff'] = '{0} {1}'.format(meshcut_glob, meshcut_units)

        return parameters

    def _get_basis(self, key, structure):
        """
        Method to construct the `basis` input.
        Heuristics are applied, a dictionary with the basis is returned.
        """
        basis = self._protocols[key]['basis'].copy()

        if 'atomic_heuristics' in self._protocols[key]:  # pylint: disable=too-many-nested-blocks
            atomic_heuristics = self._protocols[key]['atomic_heuristics']

            pol_dict = {}
            size_dict = {}

            # Run through all the heuristics
            for kind in structure.kinds:
                need_to_apply = False
                try:
                    cust_basis = atomic_heuristics[kind.symbol]['basis']
                    need_to_apply = True
                except KeyError:
                    pass
                if need_to_apply:
                    if 'split-tail-norm' in cust_basis:
                        basis['pao-split-tail-norm'] = True
                    if 'polarization' in cust_basis:
                        pol_dict[kind.name] = cust_basis['polarization']
                    if 'size' in cust_basis:
                        size_dict[kind.name] = cust_basis['size']

            if pol_dict:
                card = '\n'
                for k, v in pol_dict.items():  # pylint: disable=invalid-name
                    card = card + '  {0}  {1} \n'.format(k, v)
                card = card + '%endblock paopolarizationscheme'
                basis['%block pao-polarization-scheme'] = card
            if size_dict:
                card = '\n'
                for k, v in size_dict.items():  # pylint: disable=invalid-name
                    card = card + '  {0}  {1} \n'.format(k, v)
                card = card + '%endblock paobasessizes'
                basis['%block pao-bases-sizes'] = card

        return basis

    def _get_kpoints(self, key, structure):
        from aiida.orm import KpointsData
        if 'kpoints' in self._protocols[key]:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kp_dict = self._protocols[key]['kpoints']
            if 'offset' in kp_dict:
                kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'], offset=kp_dict['offset'])
            else:
                kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'])
        else:
            kpoints_mesh = None

        return kpoints_mesh

    def _get_pseudo_fam(self, key):
        from aiida.orm import Str
        return Str(self._protocols[key]['pseudo_family'])
