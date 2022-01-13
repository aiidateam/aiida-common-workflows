# -*- coding: utf-8 -*-
"""Implementation of the ``CommonBandsInputGenerator`` for Quantum ESPRESSO."""

from aiida import engine, orm
from aiida.common import LinkType

from aiida_common_workflows.generators import CodeType

from ..generator import CommonBandsInputGenerator

__all__ = ('QuantumEspressoCommonBandsInputGenerator',)


class QuantumEspressoCommonBandsInputGenerator(CommonBandsInputGenerator):
    """Input generator for the ``QuantumEspressoCommonBandsWorkChain``"""

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['engines']['bands']['code'].valid_type = CodeType('quantumespresso.pw')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        engines = kwargs.get('engines', None)
        parent_folder = kwargs['parent_folder']
        bands_kpoints = kwargs['bands_kpoints']

        # Find the `PwCalculation` that created the `parent_folder` and obtain the restart builder.
        parent_calc = parent_folder.get_incoming(link_type=LinkType.CREATE).one().node
        if parent_calc.process_type != 'aiida.calculations:quantumespresso.pw':
            raise ValueError('The `parent_folder` has not been created by a `PwCalculation`.')
        builder_calc = parent_calc.get_builder_restart()

        builder_common_bands_wc = self.process_class.get_builder()
        builder_calc.pop('kpoints')
        builder_common_bands_wc.pw = builder_calc
        parameters = builder_common_bands_wc.pw.parameters.get_dict()
        parameters['CONTROL']['calculation'] = 'bands'
        builder_common_bands_wc.pw.parameters = orm.Dict(dict=parameters)
        builder_common_bands_wc.kpoints = bands_kpoints
        builder_common_bands_wc.pw.parent_folder = parent_folder

        # Update the structure in case we have one in output, i.e. the `parent_calc` optimized the structure
        if 'output_structure' in parent_calc.outputs:
            builder_common_bands_wc.pw.structure = parent_calc.outputs.output_structure

        # Update the code and computational options if `engines` is specified
        try:
            bands_engine = engines['bands']
        except KeyError:
            raise ValueError('The `engines` dictionary must contain `bands` as a top-level key')
        if 'code' in bands_engine:
            code = engines['bands']['code']
            if isinstance(code, str):
                code = orm.load_code(code)
            builder_common_bands_wc.pw.code = code
        if 'options' in bands_engine:
            builder_common_bands_wc.pw.metadata.options = engines['bands']['options']

        return builder_common_bands_wc
