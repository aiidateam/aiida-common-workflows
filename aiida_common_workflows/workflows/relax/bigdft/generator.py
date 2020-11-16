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
            }
        },
        'moderate': {
            'description': 'This profile should be chosen if accurate forces are required, but there is no need for '
            'extremely accurate energies.',
            'inputdict_cubic': {},
            'inputdict_linear': {
                'import': 'linear'
            }
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
            }
        }
    }

    _calc_types = {'relax': {'code_plugin': 'bigdft.bigdft', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
    }
    _spin_types = {SpinType.NONE: '....', SpinType.COLLINEAR: '....'}
    _electronic_types = {ElectronicType.METAL: '....', ElectronicType.INSULATOR: '....'}

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

        if relax_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        builder = self.process_class.get_builder()
        builder.structure = structure

        # Will be implemented in the bigdft plugin
        # inputdict = BigDFTParameters.get_input_dict(protocol, structure, 'relax')
        # for now apply simple stupid heuristic : atoms < 200 -> cubic, else -> linear.
        if len(structure.sites) <= 200:
            inputdict = self.get_protocol(protocol)['inputdict_cubic']
        else:
            inputdict = self.get_protocol(protocol)['inputdict_linear']

        builder.parameters = BigDFTParameters(dict=inputdict)
        builder.code = orm.load_code(calc_engines[relaxation_schema]['code'])
        run_opts = {'options': calc_engines[relaxation_schema]['options']}
        builder.run_opts = orm.Dict(dict=run_opts)

        if threshold_forces is not None:
            builder.relax.threshold_forces = orm.Float(threshold_forces)

        return builder
