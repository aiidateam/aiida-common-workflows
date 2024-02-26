"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for SIESTA."""
import os

import yaml
from aiida import engine, orm, plugins
from aiida.common import exceptions

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('SiestaCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class SiestaCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Generator of inputs for the SiestaCommonRelaxWorkChain"""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError(f'invalid protocol registry `{self.__class__.__name__}`: ' + message)

        for k, v in self._protocols.items():
            if 'parameters' not in v:
                raise_invalid(f'protocol `{k}` does not define the mandatory key `parameters`')
            if 'mesh-cutoff' in v['parameters']:
                try:
                    float(v['parameters']['mesh-cutoff'].split()[0])
                    str(v['parameters']['mesh-cutoff'].split()[1])
                except (ValueError, IndexError):
                    raise_invalid(
                        f'Wrong format of `mesh-cutoff` in `parameters` of protocol `{k}`. Value and units are required'
                    )

            if 'basis' not in v:
                raise_invalid(f'protocol `{k}` does not define the mandatory key `basis`')

            if 'pseudo_family' not in v:
                raise_invalid(f'protocol `{k}` does not define the mandatory key `pseudo_family`')

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        _filepath = os.path.join(os.path.dirname(__file__), 'protocol.yml')

        with open(_filepath, encoding='utf-8') as _thefile:
            self._protocols = yaml.full_load(_thefile)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['protocol'].valid_type = ChoiceType(('fast', 'moderate', 'precise', 'verification-PBE-v1'))
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            (RelaxType.NONE, RelaxType.POSITIONS, RelaxType.POSITIONS_CELL, RelaxType.POSITIONS_SHAPE)
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('siesta.siesta')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # Checks
        if protocol not in self.get_protocol_names():
            import warnings

            warnings.warn(f'no protocol implemented with name {protocol}, using default moderate')
            protocol = self.get_default_protocol_name()
        if 'relax' not in engines:
            raise ValueError('The `engines` dictionaly must contain "relax" as outermost key')

        pseudo_family = self._protocols[protocol]['pseudo_family']
        try:
            orm.Group.collection.get(label=pseudo_family)
        except exceptions.NotExistent as exc:
            raise ValueError(
                f'protocol `{protocol}` requires `pseudo_family` with name {pseudo_family} '
                'but no family with this name is loaded in the database'
            ) from exc

        # K points
        kpoints_mesh = self._get_kpoints(protocol, structure, reference_workchain)

        # Parameters, including scf ...
        parameters = self._get_param(protocol, structure, reference_workchain)
        # ... relax options ...
        if relax_type != RelaxType.NONE:
            parameters['md-type-of-run'] = 'cg'
            parameters['md-num-cg-steps'] = 100
        if relax_type == RelaxType.POSITIONS_CELL:
            parameters['md-variable-cell'] = True
        if relax_type == RelaxType.POSITIONS_SHAPE:
            parameters['md-variable-cell'] = True
            parameters['md-constant-volume'] = True
        if threshold_forces:
            parameters['md-max-force-tol'] = str(threshold_forces) + ' eV/Ang'
        if threshold_stress:
            parameters['md-max-stress-tol'] = str(threshold_stress) + ' eV/Ang**3'
        # ... spin options (including initial magentization) ...
        if spin_type == SpinType.COLLINEAR:
            parameters['spin'] = 'polarized'
        if magnetization_per_site is not None:
            if spin_type == SpinType.NONE:
                import warnings

                warnings.warn('`magnetization_per_site` will be ignored as `spin_type` is set to SpinType.NONE')
            if spin_type == SpinType.COLLINEAR:
                in_spin_card = '\n'
                for i, magn in enumerate(magnetization_per_site):
                    in_spin_card += f' {i+1} {magn} \n'
                in_spin_card += '%endblock dm-init-spin'
                parameters['%block dm-init-spin'] = in_spin_card

        # Basis
        basis = self._get_basis(protocol, structure)

        # Pseudo fam
        pseudo_family = self._get_pseudo_fam(protocol)

        builder = self.process_class.get_builder()
        builder.structure = structure
        builder.basis = orm.Dict(dict=basis)
        builder.parameters = orm.Dict(dict=parameters)
        if kpoints_mesh:
            builder.kpoints = kpoints_mesh
        builder.pseudo_family = pseudo_family
        builder.options = orm.Dict(dict=engines['relax']['options'])
        builder.code = engines['relax']['code']

        return builder

    def _get_param(self, key, structure, reference_workchain):  # noqa: PLR0912
        """
        Method to construct the `parameters` input. Heuristics are applied, a dictionary
        with the parameters is returned.
        """
        parameters = self._protocols[key]['parameters'].copy()
        for par, value in self._protocols[key]['parameters'].items():
            if 'block' in par:
                parameters['%' + par] = value
                parameters.pop(par, None)

        if 'atomic_heuristics' in self._protocols[key]:
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
                        except (ValueError, IndexError) as exc:
                            raise RuntimeError(
                                f'Wrong `mesh-cutoff` value for heuristc {kind.symbol} of protocol {key}'
                            ) from exc
                        if meshcut_glob is not None:
                            if cust_meshcut > float(meshcut_glob):
                                meshcut_glob = cust_meshcut
                        else:
                            meshcut_glob = cust_meshcut
                            try:
                                meshcut_units = cust_param['mesh-cutoff'].split()[1]
                            except (ValueError, IndexError) as exc:
                                raise RuntimeError(
                                    f'Wrong `mesh-cutoff` units for heuristc {kind.symbol} of protocol {key}'
                                ) from exc
                    if 'grid-sampling' in cust_param:
                        parameters['%block GridCellSampling'] = (
                            cust_param['grid-sampling'] + '\n%endblock GridCellSampling'
                        )

            if meshcut_glob is not None:
                parameters['mesh-cutoff'] = f'{meshcut_glob} {meshcut_units}'

        # We fix the `mesh-sizes` to the one of reference_workchain, we need to access
        # the underline SiestaBaseWorkChain.
        if reference_workchain is not None:
            from aiida.orm import WorkChainNode

            siesta_base_outs = reference_workchain.base.links.get_outgoing(node_class=WorkChainNode).one().node.outputs
            mesh = siesta_base_outs.output_parameters.base.attributes.get('mesh')
            parameters['mesh-sizes'] = f'[{mesh[0]} {mesh[1]} {mesh[2]}]'
            parameters.pop('mesh-cutoff', None)

        return parameters

    def _get_basis(self, key, structure):  # noqa: PLR0912
        """
        Method to construct the `basis` input.
        Heuristics are applied, a dictionary with the basis is returned.
        """
        basis = self._protocols[key]['basis'].copy()

        if 'atomic_heuristics' in self._protocols[key]:
            atomic_heuristics = self._protocols[key]['atomic_heuristics']

            pol_dict = {}
            size_dict = {}
            pao_block_dict = {}

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
                    if 'pao-block' in cust_basis:
                        pao_block_dict[kind.name] = cust_basis['pao-block']
                        if kind.name != kind.symbol:
                            pao_block_dict[kind.name] = pao_block_dict[kind.name].replace(kind.symbol, kind.name)

            if pol_dict:
                card = '\n'
                for k, value in pol_dict.items():
                    card = card + f'  {k}  {value} \n'
                card = card + '%endblock paopolarizationscheme'
                basis['%block pao-polarization-scheme'] = card
            if size_dict:
                card = '\n'
                for k, value in size_dict.items():
                    card = card + f'  {k}  {value} \n'
                card = card + '%endblock paobasissizes'
                basis['%block pao-basis-sizes'] = card
            if pao_block_dict:
                card = '\n'
                for k, value in pao_block_dict.items():
                    card = card + f'{value} \n'
                card = card + '%endblock pao-basis'
                basis['%block pao-basis'] = card

        return basis

    def _get_kpoints(self, key, structure, reference_workchain):
        from aiida.orm import KpointsData

        if reference_workchain:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            previous_wc_kp = reference_workchain.inputs.kpoints
            kpoints_mesh.set_kpoints_mesh(
                previous_wc_kp.base.attributes.get('mesh'), previous_wc_kp.base.attributes.get('offset')
            )
            return kpoints_mesh

        if 'kpoints' in self._protocols[key]:
            kpoints_mesh = KpointsData()
            kpoints_mesh.set_cell_from_structure(structure)
            kp_dict = self._protocols[key]['kpoints']
            if 'offset' in kp_dict:
                kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'], offset=kp_dict['offset'])
            else:
                kpoints_mesh.set_kpoints_mesh_from_density(distance=kp_dict['distance'])
            return kpoints_mesh

        return None

    def _get_pseudo_fam(self, key):
        from aiida.orm import Str

        return Str(self._protocols[key]['pseudo_family'])
