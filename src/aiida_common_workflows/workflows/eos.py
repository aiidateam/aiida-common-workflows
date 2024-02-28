"""Equation of state workflow that can use any code plugin implementing the common relax workflow."""
import inspect

from aiida import orm
from aiida.common import exceptions
from aiida.engine import WorkChain, append_, calcfunction
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.relax.generator import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def validate_inputs(value, _):
    """Validate the entire input namespace."""
    if 'scale_factors' not in value:
        if 'scale_count' not in value or 'scale_increment' not in value:
            return 'neither `scale_factors` nor the pair of `scale_count` and `scale_increment` were defined.'

    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['sub_process_class'])
    generator = process_class.get_input_generator()

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


def validate_scale_factors(value, _):
    """Validate the `validate_scale_factors` input."""
    if value and len(value) < 3:
        return 'need at least 3 scaling factors.'


def validate_scale_count(value, _):
    """Validate the `scale_count` input."""
    if value is not None and value < 3:
        return 'need at least 3 scaling factors.'


def validate_scale_increment(value, _):
    """Validate the `scale_increment` input."""
    if value is not None and not 0 < value < 1:
        return 'scale increment needs to be between 0 and 1.'


def validate_relax_type(value, _):
    """Validate the `generator_inputs.relax_type` input."""
    if value is not None and isinstance(value, str):
        value = RelaxType(value)

    if value not in [RelaxType.NONE, RelaxType.POSITIONS, RelaxType.SHAPE, RelaxType.POSITIONS_SHAPE]:
        return '`generator_inputs.relax_type`. Equation of state and relaxation with variable volume not compatible.'


@calcfunction
def scale_structure(structure: orm.StructureData, scale_factor: orm.Float) -> orm.StructureData:
    """Scale the structure with the given scaling factor."""
    ase = structure.get_ase().copy()
    ase.set_cell(ase.get_cell() * float(scale_factor) ** (1 / 3), scale_atoms=True)
    return orm.StructureData(ase=ase)


class EquationOfStateWorkChain(WorkChain):
    """Workflow to compute the equation of state for a given crystal structure."""

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input('structure', valid_type=orm.StructureData, help='The structure at equilibrium volume.')
        spec.input('scale_factors', valid_type=orm.List, required=False,
            validator=validate_scale_factors, serializer=orm.to_aiida_type,
            help='The list of scale factors at which the volume and total energy of the structure should be computed.')
        spec.input('scale_count', valid_type=orm.Int, default=lambda: orm.Int(7),
            validator=validate_scale_count, serializer=orm.to_aiida_type,
            help='The number of points to compute for the equation of state.')
        spec.input('scale_increment', valid_type=orm.Float, default=lambda: orm.Float(0.02),
            validator=validate_scale_increment, serializer=orm.to_aiida_type,
            help='The relative difference between consecutive scaling factors.')
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
        spec.input('generator_inputs.magnetization_per_site', valid_type=(list, tuple), required=False, non_db=True,
            help='List containing the initial magnetization per atomic site.')
        spec.input('generator_inputs.threshold_forces', valid_type=float, required=False, non_db=True,
            help='Target threshold for the forces in eV/Å.')
        spec.input('generator_inputs.threshold_stress', valid_type=float, required=False, non_db=True,
            help='Target threshold for the stress in eV/Å^3.')
        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.run_init,
            cls.inspect_init,
            cls.run_eos,
            cls.inspect_eos,
        )
        spec.output_namespace('structures', valid_type=orm.StructureData,
            help='The relaxed structures at each scaling factor.')
        spec.output_namespace('total_energies', valid_type=orm.Float,
            help='The computed total energy of the relaxed structures at each scaling factor.')
        spec.output_namespace('total_magnetizations', valid_type=orm.Float,
            help='The computed total magnetization of the relaxed structures at each scaling factor.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')

    def get_scale_factors(self):
        """Return the list of scale factors."""
        if 'scale_factors' in self.inputs:
            return tuple(self.inputs.scale_factors)

        count = self.inputs.scale_count.value
        increment = self.inputs.scale_increment.value
        return tuple(float(1 + i * increment - (count - 1) * increment / 2) for i in range(count))

    def get_sub_workchain_builder(self, scale_factor, reference_workchain=None):
        """Return the builder for the relax workchain."""
        structure = scale_structure(self.inputs.structure, scale_factor)
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        base_inputs = {'structure': structure}
        if reference_workchain is not None:
            base_inputs['reference_workchain'] = reference_workchain

        builder = process_class.get_input_generator().get_builder(**base_inputs, **self.inputs.generator_inputs)
        builder._merge(**self.inputs.get('sub_process', {}))

        return builder, structure

    def run_init(self):
        """
        Run the first workchain.

        This is run for the first (usually the smallest) volume in the set of scale factors,
        which is then used as a reference workchain for all other calculations.
        Each plugin should then reuse the relevant parameters from this reference
        calculation, in particular the choice of the k-points grid.
        """
        scale_factor = orm.Float(self.get_scale_factors()[0])
        builder, structure = self.get_sub_workchain_builder(scale_factor)
        self.report(f'submitting `{builder.process_class.__name__}` for scale_factor `{scale_factor}`')
        self.ctx.reference_workchain = self.submit(builder)
        self.ctx.structures = [structure]
        self.to_context(children=append_(self.ctx.reference_workchain))

    def inspect_init(self):
        """Check that the first workchain finished successfully or abort the workchain."""
        if not self.ctx.children[0].is_finished_ok:
            self.report('Initial sub process did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)

    def run_eos(self):
        """Run the sub process at each scale factor to compute the structure volume and total energy."""
        for scale_factor in self.get_scale_factors()[1:]:
            reference_workchain = self.ctx.reference_workchain
            builder, structure = self.get_sub_workchain_builder(
                orm.Float(scale_factor), reference_workchain=reference_workchain
            )
            self.report(f'submitting `{builder.process_class.__name__}` for scale_factor `{scale_factor}`')
            self.ctx.structures.append(structure)
            self.to_context(children=append_(self.submit(builder)))

    def inspect_eos(self):
        """Inspect all children workflows to make sure they finished successfully."""
        if any(not child.is_finished_ok for child in self.ctx.children):
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)

        for index, child in enumerate(self.ctx.children):
            try:
                structure = child.outputs.relaxed_structure
            except exceptions.NotExistent:
                structure = self.ctx.structures[index]

            volume = structure.get_cell_volume()
            energy = child.outputs.total_energy

            self.report(f'Image {index}: volume={volume}, total energy={energy.value}')
            self.out(f'structures.{index}', structure)
            self.out(f'total_energies.{index}', energy)

            if 'total_magnetization' in child.outputs:
                self.out(f'total_magnetizations.{index}', child.outputs.total_magnetization)
