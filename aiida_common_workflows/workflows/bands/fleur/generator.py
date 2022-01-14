# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.bands.generator.CommonBandsInputGenerator` for Fleur."""

from aiida import engine, orm

from aiida_common_workflows.generators import CodeType

from ..generator import CommonBandsInputGenerator

__all__ = ('FleurCommonBandsInputGenerator',)


class FleurCommonBandsInputGenerator(CommonBandsInputGenerator):
    """Generator of inputs for the FleurCommonBandsWorkChain"""

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['engines']['bands']['code'].valid_type = CodeType('fleur.fleur')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        engines = kwargs.get('engines', None)
        parent_folder = kwargs['parent_folder']
        bands_kpoints = kwargs['bands_kpoints']

        # From the parent folder, we retrieve the calculation that created it.
        parent_calc = parent_folder.creator
        if parent_calc.process_type != 'aiida.calculations:fleur.fleur':
            raise ValueError('The `parent_folder` has not been created by a FleurCalculation')
        builder_parent = parent_folder.creator.get_builder_restart()

        builder = self.process_class.get_builder()
        builder.options = orm.Dict(dict=builder_parent.metadata.options)
        builder.metadata = {}
        for key, value in builder_parent.items():
            if value and key != 'metadata':
                builder[key] = value

        wf_parameters = {'kpath': 'skip'}

        builder.wf_parameters = orm.Dict(dict=wf_parameters)
        builder.kpoints = bands_kpoints
        builder.remote = parent_folder

        if engines:
            try:
                band_engines = engines['bands']
            except KeyError:
                raise ValueError('The `engines` dictionary must contain `bands` as a top-level key')
            if 'code' in band_engines:
                builder.code = band_engines['code']
            if 'options' in band_engines:
                builder.options = orm.Dict(dict=band_engines['options'])

        return builder
