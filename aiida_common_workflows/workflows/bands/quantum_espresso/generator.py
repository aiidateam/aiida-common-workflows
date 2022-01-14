# -*- coding: utf-8 -*-
"""Implementation of the ``CommonBandsInputGenerator`` for Quantum ESPRESSO."""

from aiida import engine, orm

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
        parent_calc = parent_folder.creator
        if parent_calc.process_type != 'aiida.calculations:quantumespresso.pw':
            raise ValueError('The `parent_folder` has not been created by a `PwCalculation`.')
        builder = self.process_class.get_builder()

        parameters = builder.pw.parameters.get_dict()
        parameters['CONTROL']['calculation'] = 'bands'

        # Inputs of the `pw` calcjob are based of the inputs of the `parent_folder` creator's inputs
        builder.pw = parent_folder.creator.get_builder_restart()
        builder.pw.parameters = orm.Dict(dict=parameters)
        builder.pw.parent_folder = parent_folder
        builder.pw.pop('kpoints')
        builder.kpoints = bands_kpoints

        # Update the structure in case we have one in output, i.e. the `parent_calc` optimized the structure
        if 'output_structure' in parent_calc.outputs:
            builder.pw.structure = parent_calc.outputs.output_structure

        # Update the code and computational options only if the `engines` input is provided
        if engines is None:
            return builder

        try:
            bands_engine = engines['bands']
        except KeyError:
            raise ValueError('The `engines` dictionary must contain `bands` as a top-level key')
        if 'code' in bands_engine:
            code = bands_engine['code']
            if isinstance(code, str):
                code = orm.load_code(code)
            builder.pw.code = code
        if 'options' in bands_engine:
            builder.pw.metadata.options = bands_engine['options']

        return builder
