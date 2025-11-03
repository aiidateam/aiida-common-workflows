"""Equation of state workflow that can use any code plugin implementing the common relax workflow."""
import inspect

from aiida import orm
from aiida.common import exceptions
from aiida.engine import WorkChain, append_
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.relax.generator import ElectronicType, OptionalRelaxFeatures, RelaxType, SpinType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def validate_inputs(value, _):
    """Validate the entire input namespace."""

    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['sub_process_class'])
    generator = process_class.get_input_generator()

    if not generator.supports_feature(OptionalRelaxFeatures.FIXED_MAGNETIZATION):
        return (
            f'The `{value["sub_process_class"]}` plugin does not support the '
            f'`{OptionalRelaxFeatures.FIXED_MAGNETIZATION}` optional feature required for this workflow.'
        )

    try:
        generator.get_builder(structure=value['structure'], **value['generator_inputs'])
    except Exception as exc:
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `generator_inputs`: {exc}'


def validate_sub_process_class(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value)
    except exceptions.EntryPointError:
        return f'`{value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonRelaxWorkChain):
        return f'`{value}` is not a subclass of the `CommonRelaxWorkChain` common workflow.'


def validate_total_magnetizations(value, _):
    """Validate the `fixed_total_magnetizations` input."""
    if value and len(value) < 3:
        return 'need at least 3 total magnetizations.'
    if not all(isinstance(m, (int, float)) for m in value):
        return 'all total magnetizations must be numbers (int or float).'


def validate_relax_type(value, _):
    """Validate the `generator_inputs.relax_type` input."""
    if value is not None and isinstance(value, str):
        value = RelaxType(value)

    if value not in [RelaxType.NONE, RelaxType.POSITIONS, RelaxType.SHAPE, RelaxType.POSITIONS_SHAPE]:
        return '`generator_inputs.relax_type`. Equation of state and relaxation with variable volume not compatible.'


class EnergyMagnetizationWorkChain(WorkChain):
    """Workflow to compute the energy vs magnetization curve for a given crystal structure."""

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input('structure', valid_type=orm.StructureData, help='The structure at equilibrium volume.')
        spec.input('fixed_total_magnetizations', valid_type=orm.List, required=True,
            validator=validate_total_magnetizations, serializer=orm.to_aiida_type,
            help='The list of fixed total magnetizations to be calculated for the structure.')
        spec.input_namespace('generator_inputs',
            help='The inputs that will be passed to the input generator of the specified `sub_process`.')
        spec.input('generator_inputs.engines', valid_type=dict, non_db=True)
        spec.input('generator_inputs.protocol', valid_type=str, non_db=True,
            help='The protocol to use when determining the workchain inputs.')
        spec.input('generator_inputs.relax_type',
             valid_type=(RelaxType, str), non_db=True, validator=validate_relax_type,
            help='The type of relaxation to perform.')
        spec.input('generator_inputs.spin_type', valid_type=(SpinType, str), required=False, non_db=True,
            help='The type of spin for the calculation.')
        spec.input('generator_inputs.electronic_type', valid_type=(ElectronicType, str), required=False, non_db=True,
            help='The type of electronics (insulator/metal) for the calculation.')
        spec.input('generator_inputs.threshold_forces', valid_type=float, required=False, non_db=True,
            help='Target threshold for the forces in eV/Å.')
        spec.input('generator_inputs.threshold_stress', valid_type=float, required=False, non_db=True,
            help='Target threshold for the stress in eV/Å^3.')
        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_inputs

        spec.outline(
            cls.run_em,
            cls.inspect_em,
        )

        spec.output_namespace('total_energies', valid_type=orm.Float,
            help='The computed total energy of the relaxed structures at each scaling factor.')
        spec.output_namespace('total_magnetizations', valid_type=orm.Float,
            help='The fixed total magnetizations that were evaluated.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')

    def get_sub_workchain_builder(self, total_magnetization):
        """Return the builder for the relax workchain."""
        structure = self.inputs.structure
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        base_inputs = {'structure': structure, 'fixed_total_cell_magnetization': total_magnetization}

        builder = process_class.get_input_generator().get_builder(**base_inputs, **self.inputs.generator_inputs)
        builder._merge(**self.inputs.get('sub_process', {}))

        return builder

    def run_em(self):
        """Run the sub process at each scale factor to compute the structure volume and total energy."""
        for total_magnetization in self.inputs.fixed_total_magnetizations:
            builder = self.get_sub_workchain_builder(total_magnetization)
            self.report(
                f'submitting `{builder.process_class.__name__}` for total_magnetization `{total_magnetization}`'
            )
            self.to_context(children=append_(self.submit(builder)))

    def inspect_em(self):
        """Inspect all children workflows to make sure they finished successfully."""
        if any(not child.is_finished_ok for child in self.ctx.children):
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)

        for index, child in enumerate(self.ctx.children):
            energy = child.outputs.total_energy
            total_magnetization = child.outputs.total_magnetization

            self.report(f'Image {index}: total_magnetization={total_magnetization}, total energy={energy.value}')

            self.out(f'total_energies.{index}', energy)
            self.out(f'total_magnetizations.{index}', total_magnetization)
