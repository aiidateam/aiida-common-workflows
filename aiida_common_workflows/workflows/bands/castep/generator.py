# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.bands.generator.CommonBandsInputGenerator` for CASTEP."""
from aiida import engine, orm

from aiida_common_workflows.generators import CodeType

from ..generator import CommonBandsInputGenerator

__all__ = ('CastepCommonBandsInputGenerator',)


class CastepCommonBandsInputGenerator(CommonBandsInputGenerator):
    """Generator of inputs for the CastepCommonBandsWorkChain"""

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['engines']['bands']['code'].valid_type = CodeType('castep.castep')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals

        required_keys = ('engines', 'parent_folder', 'bands_kpoints')
        for key in required_keys:
            if key not in kwargs:
                raise ValueError(f'Required key `{key}` is missing in the function argument.')
        engines = kwargs['engines']
        parent_folder = kwargs['parent_folder']
        bands_kpoints = kwargs['bands_kpoints']

        # From the parent folder, we retrieve the calculation that created it. Note
        # that we are sure it exists (it wouldn't be the same for WorkChains). We then check
        # that it is a CastepCalculation and create the builder.
        parent_castep_calc = parent_folder.creator
        if parent_castep_calc.process_type != 'aiida.calculations:castep.castep':
            raise ValueError('The `parent_folder` has not been created by a CastepCalculation')
        builder_castep_calc = parent_castep_calc.get_builder_restart()

        # Construct the builder of the `common_bands_wc` from the builder of a CastepCalculation.
        builder_common_bands_wc = self.process_class.get_builder()
        builder_common_bands_wc.scf.calc_options = orm.Dict(dict=dict(builder_castep_calc.metadata.options))
        # Ensure we use castep_bin for restart, instead of the check file
        #builder_common_bands_wc.scf.options = orm.Dict(dict={'use_castep_bin': True})

        builder_castep_calc.metadata = {}

        # Attach inputs of the calculation
        for key, value in builder_castep_calc.items():
            if value and key not in ['metadata', 'structure']:
                builder_common_bands_wc.scf.calc[key] = value

        # Updated the structure (in case we have one in output)
        if 'output_structure' in parent_castep_calc.outputs:
            builder_common_bands_wc.structure = parent_castep_calc.outputs.output_structure
        else:
            builder_common_bands_wc.structure = parent_castep_calc.inputs.structure

        try:
            engb = engines['bands']
        except KeyError:
            raise ValueError('The engines dictionary passed must contains a key named `bands`.')

        builder_common_bands_wc.scf.calc.code = engb['code']

        if 'options' in engb:
            builder_common_bands_wc.scf.calc.metadata.options = engb['options']

        # Set the `bandskpoints` and the `parent_calc_folder` for restart
        builder_common_bands_wc.bands_kpoints = bands_kpoints
        builder_common_bands_wc.scf.continuation_folder = parent_folder
        builder_common_bands_wc.run_separate_scf = orm.Bool(False)

        return builder_common_bands_wc
