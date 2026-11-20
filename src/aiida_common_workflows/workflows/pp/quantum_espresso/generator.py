"""
Implementation of `aiida_common_workflows.common.pp.generator.CommonPostProcessInputGenerator` for Quantum ESPRESSO.
"""

from aiida import engine

from ..generator import CommonPostProcessInputGenerator

__all__ = ('QuantumEspressoCommonPostProcessInputGenerator',)


class QuantumEspressoCommonPostProcessInputGenerator(CommonPostProcessInputGenerator):
    """Input generator for the common post-processing workflow implementation of Quantum ESPRESSO."""

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        from aiida_quantumespresso.common.types import PostProcessQuantity

        # Convert to aiida-quantumespresso PostProcessQuantity
        quantity = kwargs['quantity']
        if isinstance(quantity, str):
            quantity = PostProcessQuantity(quantity)
        else:  # is ACWF's PostProcessQuantity
            quantity = PostProcessQuantity(quantity.value)

        process_class = self.process_class._process_class
        builder = process_class.get_builder_from_quantity(
            code=kwargs['engines']['pp']['code'],
            quantity=quantity,
            parent_folder=kwargs['parent_folder'],
            options=kwargs['engines']['pp'].get('options', {}),
        )
        builder._process_class = self.process_class
        return builder
