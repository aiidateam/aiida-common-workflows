# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for BigDFT."""
from aiida import orm

from ..generator import RelaxInputsGenerator, RelaxType
from aiida.plugins import WorkflowFactory, DataFactory

__all__ = ('BigDFTRelaxInputsGenerator',)

BigDFTRelaxWorkChain = WorkflowFactory('bigdft.relax')
BigDFTParameters = DataFactory('bigdft')

class BigDFTRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `BigDFTRelaxWorkChain`."""

    _default_protocol = 'efficiency'
    _protocols = {'efficiency': {'description': '', 'inputdict': {}}, 'precision': {'description': '', 'inputdict': {}}}

    _calc_types = {'relax': {'code_plugin': 'bigdft.bigdft', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
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
        from aiida_bigdft.workflows.relax import BigDFTRelaxWorkChain
        from aiida.orm import (Str, Dict)
        from aiida.orm import load_code

        #parameters = protocol_dict["parameters"].copy()

        #Pseudo fam
        #pseudo_fam = kwargs.pop('pseudo_family')
        if relaxation_type == RelaxType.ATOMS:
            relaxation_schema = 'relax'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        builder = BigDFTRelaxWorkChain.get_builder()
        builder.structure = structure
        builder.parameters = BigDFTParameters(dict=self.get_protocol(protocol)['inputdict'])
        #builder.pseudos = Str(pseudo_fam)
        #builder.options = Dict(dict=calc_engines["relaxation"]["options"])
        builder.code = load_code(calc_engines['relax']['code'])
        run_opts={
            'options': calc_engines['relax']['options']
        }
        builder.run_opts=Dict(dict=run_opts)


        if threshold_forces is not None:
            builder.relax.threshold_forces=orm.Float(threshold_forces)

        # if threshold_stress is not None:
        #     parameters = builder.base.parameters.get_dict()
        #     parameters.setdefault('CELL', {})['press_conv_thr'] = threshold_stress
        #     builder.base.parameters = orm.Dict(dict=parameters)

        return builder
