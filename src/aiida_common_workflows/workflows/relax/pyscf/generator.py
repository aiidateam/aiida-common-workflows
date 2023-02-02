"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for pyscf."""
import pathlib
import warnings

import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('PyscfCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')


class PyscfCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the common relax workflow implementation of pyscf."""

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        process_class = kwargs.get('process_class', None)
        super().__init__(*args, **kwargs)
        self._initialize_protocols()

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with (pathlib.Path(__file__).parent / 'protocol.yml').open() as handle:
            self._protocols = yaml.safe_load(handle)
            self._default_protocol = 'moderate'

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE, RelaxType.POSITIONS))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('pyscf.base')

    def _construct_builder(
        self,
        structure,
        engines,
        protocol,
        spin_type,
        relax_type,
        electronic_type,
        magnetization_per_site=None,
        **kwargs,
    ) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """
        if not self.is_valid_protocol(protocol):
            raise ValueError(
                f'selected protocol {protocol} is not valid, please choose from: {", ".join(self.get_protocol_names())}'
            )

        protocol_inputs = self.get_protocol(protocol)
        parameters = protocol_inputs.pop('parameters')

        if relax_type == RelaxType.NONE:
            parameters.pop('optimizer')

        if spin_type == SpinType.COLLINEAR:
            parameters['mean_field']['method'] = 'DKS'
            parameters['mean_field']['collinear'] = 'mcol'

        num_electrons = structure.get_pymatgen_molecule().nelectrons

        if spin_type == SpinType.NONE and num_electrons % 2 == 1:
            raise ValueError('structure has odd number of electrons, please select `spin_type = SpinType.COLLINEAR`')

        if spin_type == SpinType.COLLINEAR:
            if magnetization_per_site is None:
                multiplicity = 1
            else:
                warnings.warn('magnetization_per_site site-resolved info is disregarded, only total spin is processed.')
                # ``magnetization_per_site`` is in units of Bohr magnetons, multiple by 0.5 to get atomic units
                total_spin = 0.5 * abs(sum(magnetization_per_site))
                multiplicity = 2 * total_spin + 1

            # In case of even/odd electrons, find closest odd/even multiplicity
            if num_electrons % 2 == 0:
                # round guess to nearest odd integer
                spin_multiplicity = int(round((multiplicity - 1) / 2) * 2 + 1)
            else:
                # round guess to nearest even integer; 0 goes to 2
                spin_multiplicity = max([int(round(multiplicity / 2) * 2), 2])

            parameters['structure']['spin'] = int((spin_multiplicity - 1) / 2)

        builder = self.process_class.get_builder()
        builder.pyscf.code = engines['relax']['code']
        builder.pyscf.structure = structure
        builder.pyscf.parameters = orm.Dict(parameters)
        builder.pyscf.metadata.options = engines['relax']['options']

        return builder
