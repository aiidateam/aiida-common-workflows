# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Quantum ESPRESSO."""
from typing import Any, Dict, List

from aiida import engine
from aiida import orm
from aiida import plugins

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('QuantumEspressoRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class QuantumEspressoRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `QuantumEspressoRelaxWorkChain`."""

    _calc_types = {'relax': {'code_plugin': 'quantumespresso.pw', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {relax_type: '...' for relax_type in RelaxType}
    _spin_types = {
        SpinType.NONE: 'Treat the system without spin polarization.',
        SpinType.COLLINEAR: 'Treat the system with spin polarization.'
    }
    _electronic_types = {
        ElectronicType.METAL: 'Treat the system as a metal with smeared occupations.',
        ElectronicType.INSULATOR: 'Treat the system as an insulator with fixed occupations.'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
        process_class = kwargs.get('process_class', None)

        if process_class is not None:
            self._default_protocol = process_class._process_class.get_default_protocol()
            self._protocols = process_class._process_class.get_available_protocols()

        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        self._default_protocol = self.process_class.get_default_protocol()
        self._protocols = self.process_class.get_available_protocols()

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
        reference_workchain=None,
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
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        from aiida_quantumespresso.common import types
        from qe_tools import CONSTANTS

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
            reference_workchain=reference_workchain,
            **kwargs
        )

        if magnetization_per_site:
            kind_to_magnetization = zip([site.kind_name for site in structure.sites], magnetization_per_site)

            if len(structure.kinds) != len(set(kind_to_magnetization)):
                raise ValueError(
                    'the provided `magnetization_per_site` requires the structure to have different kinds, which would '
                    'require changing the structure, which is not yet supported. Either manually adapt the structure '
                    'to support the required kinds or adapt the `magnetization_per_site`. The sites of each kind need '
                    'to start with the exact same magnetization. There is no threshold to compare float numbers, i.e., '
                    'starting magnetizations 0.1 and 0.0999999999 are considered different.'
                )

            initial_magnetic_moments = dict(kind_to_magnetization)
        else:
            initial_magnetic_moments = None

        builder = self.process_class._process_class.get_builder_from_protocol(  # pylint: disable=protected-access
            calc_engines['relax']['code'],
            structure,
            protocol=protocol,
            overrides={
                'base': {
                    'pw': {
                        'metadata': {
                            'options': calc_engines['relax']['options']
                        }
                    }
                },
            },
            relax_type=types.RelaxType(relax_type.value),
            electronic_type=types.ElectronicType(electronic_type.value),
            spin_type=types.SpinType(spin_type.value),
            initial_magnetic_moments=initial_magnetic_moments,
        )

        if threshold_forces is not None:
            threshold = threshold_forces * CONSTANTS.bohr_to_ang / CONSTANTS.ry_to_ev
            parameters = builder.base.pw['parameters'].get_dict()
            parameters.setdefault('CONTROL', {})['forc_conv_thr'] = threshold
            builder.base.pw['parameters'] = orm.Dict(dict=parameters)

        if threshold_stress is not None:
            threshold = threshold_stress * CONSTANTS.bohr_to_ang**3 / CONSTANTS.ry_to_ev
            parameters = builder.base.pw['parameters'].get_dict()
            parameters.setdefault('CELL', {})['press_conv_thr'] = threshold
            builder.base.pw['parameters'] = orm.Dict(dict=parameters)

        if reference_workchain:
            relax = reference_workchain.get_outgoing(node_class=orm.WorkChainNode).one().node
            base = sorted(relax.called, key=lambda x: x.ctime)[-1]
            calc = sorted(base.called, key=lambda x: x.ctime)[-1]
            kpoints = calc.inputs.kpoints

            builder.base.pop('kpoints_distance', None)
            builder.base.pop('kpoints_force_parity', None)
            builder.base_final_scf.pop('kpoints_distance', None)
            builder.base_final_scf.pop('kpoints_force_parity', None)

            builder.base['kpoints'] = kpoints
            builder.base_final_scf['kpoints'] = kpoints

        # Currently the builder is set for the `PwRelaxWorkChain`, but we should return one for the wrapper workchain
        # `QuantumEspressoRelaxWorkChain` for which this inputs generator is built
        builder._process_class = self.process_class  # pylint: disable=protected-access

        return builder
