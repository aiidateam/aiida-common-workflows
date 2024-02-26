"""Implementation of `aiida_common_workflows.common.bands.generator.CommonBandsInputGenerator` for SIESTA."""
from aiida import engine, orm

from aiida_common_workflows.generators import CodeType

from ..generator import CommonBandsInputGenerator

__all__ = ('SiestaCommonBandsInputGenerator',)


class SiestaCommonBandsInputGenerator(CommonBandsInputGenerator):
    """Generator of inputs for the SiestaCommonBandsWorkChain"""

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['engines']['bands']['code'].valid_type = CodeType('siesta.siesta')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        engines = kwargs.get('engines', None)
        parent_folder = kwargs['parent_folder']
        bands_kpoints = kwargs['bands_kpoints']

        # From the parent folder, we retrieve the calculation that created it. Note
        # that we are sure it exists (it wouldn't be the same for WorkChains). We then check
        # that it is a SiestaCalculation and create the builder.
        parent_siesta_calc = parent_folder.creator
        if parent_siesta_calc.process_type != 'aiida.calculations:siesta.siesta':
            raise ValueError('The `parent_folder` has not been created by a SiestaCalculation')
        builder_siesta_calc = parent_siesta_calc.get_builder_restart()

        # Construct the builder of the `common_bands_wc` from the builder of a SiestaCalculation.
        # Siesta specific: we have to eampty the metadata and put the resources in `options`.
        builder_common_bands_wc = self.process_class.get_builder()
        builder_common_bands_wc.options = orm.Dict(dict=dict(builder_siesta_calc.metadata.options))
        builder_siesta_calc.metadata = {}
        for key, value in builder_siesta_calc.items():
            if value and key != 'metadata':
                builder_common_bands_wc[key] = value

        # Updated the structure (in case we have one in output)
        if 'output_structure' in parent_siesta_calc.outputs:
            builder_common_bands_wc.structure = parent_siesta_calc.outputs.output_structure

        engb = engines['bands']
        builder_common_bands_wc.code = engines['bands']['code']
        if 'options' in engb:
            builder_common_bands_wc.options = orm.Dict(dict=engines['bands']['options'])

        # Set the `bandskpoints` and the `parent_calc_folder` for restart
        builder_common_bands_wc.bandskpoints = bands_kpoints
        builder_common_bands_wc.parent_calc_folder = parent_folder

        return builder_common_bands_wc
