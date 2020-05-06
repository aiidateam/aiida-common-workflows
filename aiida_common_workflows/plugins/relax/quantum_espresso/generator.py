# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Quantum ESPRESSO."""
from aiida import orm

from aiida_common_workflows.common.relax import RelaxInputsGenerator, RelaxType
from .workchain import QuantumEspressoRelaxWorkChain

__all__ = ('QuantumEspressoRelaxInputsGenerator',)


class QuantumEspressoRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `QuantumEspressoRelaxWorkChain`."""

    _default_protocol = 'efficiency'
    _protocols = {'efficiency': {'description': ''}, 'precision': {'description': ''}}

    _calc_types = {'relax': {'code_plugin': 'quantumespresso.pw', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
    }

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
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        from aiida_quantumespresso_epfl.common.protocol.pw import generate_inputs  # pylint: disable=import-error

        code = calc_engines['relax']['code']
        process_class = QuantumEspressoRelaxWorkChain._process_class  # pylint: disable=protected-access
        pseudo_family = kwargs.pop('pseudo_family')

        builder = QuantumEspressoRelaxWorkChain.get_builder()
        inputs = generate_inputs(process_class, protocol, code, structure, pseudo_family, override={'relax': {}})
        builder._update(inputs)  # pylint: disable=protected-access

        if relaxation_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        elif relaxation_type == RelaxType.ATOMS_CELL:
            relaxation_schema = 'vc-relax'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        builder.relaxation_scheme = orm.Str(relaxation_schema)

        if threshold_forces is not None:
            parameters = builder.base.parameters.get_dict()
            parameters.setdefault('CONTROL', {})['forc_conv_thr'] = threshold_forces
            builder.base.parameters = orm.Dict(dict=parameters)

        if threshold_stress is not None:
            parameters = builder.base.parameters.get_dict()
            parameters.setdefault('CELL', {})['press_conv_thr'] = threshold_stress
            builder.base.parameters = orm.Dict(dict=parameters)

        return builder
