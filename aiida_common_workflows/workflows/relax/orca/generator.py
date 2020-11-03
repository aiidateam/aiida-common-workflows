# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Orca."""

import os
import yaml

from aiida.orm import load_code, Dict
from aiida.plugins import DataFactory

from ..generator import RelaxInputsGenerator, RelaxType

__all__ = ('OrcaRelaxInputsGenerator',)

StructureData = DataFactory('structure')


class OrcaRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `OrcaRelaxWorkChain`."""

    _default_protocol = 'moderate'

    _calc_types = {'relax': {'code_plugin': 'orca_main', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relaxing the geometry of molecule',
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError('invalid protocol registry `{}`: '.format(self.__class__.__name__) + message)

        for k, v in self._protocols.items():  # pylint: disable=invalid-name

            if 'input_keywords' not in v:
                raise_invalid('protocol `{}` does not define the mandatory key `input_keywords`'.format(k))

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        yamlpath = os.path.join(os.path.dirname(__file__), 'protocols.yaml')

        with open(yamlpath) as handler:
            self._protocols = yaml.safe_load(handler)

    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        previous_workchain=None,
        **kwargs
    ):  # pylint: disable=too-many-locals

        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            **kwargs
        )

        # Checks
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        if 'relax' not in calc_engines:
            raise ValueError('The `calc_engines` dictionaly must contain "relaxation" as outermost key')

        params = self._get_params(protocol)

        builder = self.process_class.get_builder()
        builder.orca.structure = structure
        builder.orca.parameters = Dict(dict=params)
        builder.orca.code = load_code(calc_engines['relax']['code'])
        builder.orca.metadata.options = calc_engines['relax']['options']
        return builder

    def _get_params(self, key):
        return self._protocols[key]


#EOF
