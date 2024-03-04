"""
Workflow calculating the dissociation curve of diatomic molecules.
It can use any code plugin implementing the common relax workflow.
"""
import inspect

from aiida import orm
from aiida.common import exceptions
from aiida.engine import WorkChain, append_, calcfunction
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.relax.generator import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def validate_inputs(value, _):
    """Validate the entire input namespace."""
    if 'distances' not in value:
        if any(key not in value for key in ['distances_count', 'distance_min', 'distance_max']):
            return 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
        if value['distance_min'] >= value['distance_max']:
            return '`distance_min` must be smaller than `distance_max`'

    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['sub_process_class'])
    generator = process_class.get_input_generator()

    try:
        generator.get_builder(structure=value['molecule'], **value['generator_inputs'])
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


def validate_molecule(value, _):
    """Validate the `molecule` input."""
    if len(value.sites) != 2:
        return '`molecule`. only diatomic molecules are supported.'


def validate_distances(value, _):
    """Validate the `dinstances` input."""
    if value and len(value) < 2:
        return 'need at least 2 distances.'
    if value:
        for dist in value:
            if dist < 0.0:
                return 'distances must be positive.'


def validate_distances_count(value, _):
    """Validate the `dinstances_count` input."""
    if value is not None and value < 2:
        return 'need at least 2 distances.'


def validate_distance_max(value, _):
    """Validate the `distance_max` input."""
    if value is not None and value <= 0:
        return '`distance_max` must be bigger than zero.'


def validate_distance_min(value, _):
    """Validate the `distance_min` input."""
    if value is not None and value < 0:
        return '`distance_min` must be bigger than zero.'


def validate_relax(value, _):
    """Validate the `generator_inputs.relax_type` input."""
    if value is not None and isinstance(value, str):
        value = RelaxType(value)

    if value is not RelaxType.NONE:
        return '`generator_inputs.relax_type`. Only `RelaxType.NONE` supported.'


@calcfunction
def set_distance(molecule: orm.StructureData, distance: orm.Float) -> orm.StructureData:
    """
    Move both sites of the molecule to symmetric points around the origin which are on the line connecting the original
    sites and which are separated by the target distance.
    """
    import numpy as np

    vector_diff = np.array(molecule.sites[1].position) - np.array(molecule.sites[0].position)
    versor_diff = vector_diff / np.linalg.norm(vector_diff)
    new_molecule = molecule.clone()
    new_position = (distance.value * versor_diff) / 2
    new_molecule.base.attributes.get('sites')[0]['position'] = -new_position
    new_molecule.base.attributes.get('sites')[1]['position'] = new_position
    return new_molecule


class DissociationCurveWorkChain(WorkChain):
    """Workflow to compute the dissociation curve of for a given diatomic molecule."""

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input('molecule', valid_type=orm.StructureData, validator=validate_molecule, help='The input molecule.')
        spec.input('distances', valid_type=orm.List, required=False, validator=validate_distances,
            help='The list of distances in Ångstrom at which the total energy of the molecule should be computed.')
        spec.input('distances_count', valid_type=orm.Int, default=lambda: orm.Int(20),
            validator=validate_distances_count,
            help='The number of points to compute in the dissociation curve.')
        spec.input('distance_min', valid_type=orm.Float, default=lambda: orm.Float(0.5),
            validator=validate_distance_min,
            help='The minimum tested distance in Ångstrom.')
        spec.input('distance_max', valid_type=orm.Float, default=lambda: orm.Float(3),
            validator=validate_distance_max,
            help='The maximum tested distance in Ångstrom.')
        spec.input_namespace('generator_inputs',
            help='The inputs that will be passed to the input generator of the specified `sub_process`.')
        spec.input('generator_inputs.engines', valid_type=dict, non_db=True)
        spec.input('generator_inputs.protocol', valid_type=str, non_db=True,
            help='The protocol to use when determining the workchain inputs.')
        spec.input('generator_inputs.relax_type', valid_type=(RelaxType, str), non_db=True, validator=validate_relax,
            help='The type of relaxation to perform.')
        spec.input('generator_inputs.spin_type', valid_type=(SpinType, str), required=False, non_db=True,
            help='The type of spin for the calculation.')
        spec.input('generator_inputs.electronic_type', valid_type=(ElectronicType, str), required=False, non_db=True,
            help='The type of electronics (insulator/metal) for the calculation.')
        spec.input('generator_inputs.magnetization_per_site', valid_type=(list, tuple), required=False, non_db=True,
            help='List containing the initial magnetization fer each site.')
        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.run_init,
            cls.inspect_init,
            cls.run_dissociation,
            cls.inspect_results,
        )
        spec.output_namespace('distances', valid_type=orm.Float,
            help='The distance between the two atoms.')
        spec.output_namespace('total_energies', valid_type=orm.Float,
            help='The computed total energy of the molecule at each distance.')
        spec.output_namespace('total_magnetizations', valid_type=orm.Float,
            help='The computed total magnetization of the molecule at each distance.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')

    def get_distances(self):
        """Return the list of scale factors."""
        if 'distances' in self.inputs:
            return [orm.Float(i) for i in self.inputs.distances]

        count = self.inputs.distances_count.value
        maximum = self.inputs.distance_max.value
        minimum = self.inputs.distance_min.value
        return [orm.Float(minimum + i * (maximum - minimum) / (count - 1)) for i in range(count)]

    def get_sub_workchain_builder(self, distance, reference_workchain=None):
        """Return the builder for the relax workchain."""
        molecule = set_distance(self.inputs.molecule, distance)
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        builder = process_class.get_input_generator().get_builder(
            structure=molecule, reference_workchain=reference_workchain, **self.inputs.generator_inputs
        )
        builder._merge(**self.inputs.get('sub_process', {}))

        distance_node = molecule.creator.inputs.distance

        return builder, distance_node

    def run_init(self):
        """Run the first workchain."""
        distance = self.get_distances()[0]
        builder, distance_node = self.get_sub_workchain_builder(distance)
        self.ctx.distance_nodes = [distance_node]
        self.report(f'submitting `{builder.process_class.__name__}` for distance `{distance.value}`')
        self.ctx.reference_workchain = self.submit(builder)
        self.to_context(children=append_(self.ctx.reference_workchain))

    def inspect_init(self):
        """Check that the first workchain finished successfully or abort the workchain."""
        if not self.ctx.children[0].is_finished_ok:
            self.report('Initial sub process did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)

    def run_dissociation(self):
        """Run the sub process at each distance to compute the total energy."""
        for distance in self.get_distances()[1:]:
            reference_workchain = self.ctx.reference_workchain
            builder, distance_node = self.get_sub_workchain_builder(distance, reference_workchain=reference_workchain)
            self.ctx.distance_nodes.append(distance_node)
            self.report(f'submitting `{builder.process_class.__name__}` for dinstance `{distance.value}`')
            self.to_context(children=append_(self.submit(builder)))

    def inspect_results(self):
        """
        Inspect all children workflows to make sure they finished successfully.
        Collect the total energies and return an array with the results.
        """
        if any(not child.is_finished_ok for child in self.ctx.children):
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)

        for index, child in enumerate(self.ctx.children):
            energy = child.outputs.total_energy
            distance = self.ctx.distance_nodes[index]

            self.report(f'Image {index}: distance={distance.value}, total energy={energy.value}')
            self.out(f'distances.{index}', distance)
            self.out(f'total_energies.{index}', energy)

            if 'total_magnetization' in child.outputs:
                self.out(f'total_magnetizations.{index}', child.outputs.total_magnetization)
