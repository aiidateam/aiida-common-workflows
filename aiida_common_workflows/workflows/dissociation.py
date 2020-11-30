# -*- coding: utf-8 -*-
"""
Workflow calculating the dissociation curve of diatomic molecules.
It can use any code plugin implementing the common relax workflow.
"""
import inspect
from aiida import orm
from aiida.common import exceptions
from aiida.engine import WorkChain, append_, calcfunction
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.workflows.relax.generator import RelaxType, SpinType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def validate_inputs(value, _):
    """Validate the entire input namespace."""
    if 'distances' not in value:
        if any(key not in value for key in ['distances_count', 'distance_min', 'distance_max']):
            return 'neither `distances` nor the `distances_count`, `distance_min`, and `distance_max` set were defined.'
    if 'distance_min' in value:
        if value['distance_min'] >= value['distance_max']:
            return '`distance_min` must be smaller than `distance_max`'


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
    if value is not RelaxType.NONE:
        return '`generator_inputs.relax_type`. Only `RelaxType.NONE` supported.'


@calcfunction
def set_distance(molecule: orm.StructureData, distance: orm.Float) -> orm.StructureData:
    """
    Move the second site of the molecule to meet a target distance
    between the two sites of the molecule.
    """
    import numpy as np
    vector_diff = np.array(molecule.sites[1].position) - np.array(molecule.sites[0].position)
    versor_diff = vector_diff / np.linalg.norm(vector_diff)
    molecule_new = molecule.clone()
    new_position = np.array(molecule.sites[0].position) + distance.value * versor_diff
    molecule_new.attributes['sites'][1]['position'] = new_position
    return molecule_new


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
        spec.input_namespace('generator_inputs', dynamic=True,
            help='The inputs that will be passed to the inputs generator of the specified `sub_process`.')
        spec.input('generator_inputs.calc_engines', valid_type=dict, non_db=True)
        spec.input('generator_inputs.protocol', valid_type=str, non_db=True,
            help='The protocol to use when determining the workchain inputs.')
        spec.input('generator_inputs.relax_type', valid_type=RelaxType, non_db=True, validator=validate_relax,
            help='The type of relaxation to perform.')
        spec.input('generator_inputs.spin_type', valid_type=SpinType, required=False, non_db=True,
            help='The type of spin for the calculation.')
        spec.input('generator_inputs.magnetization_per_site', valid_type=(list, tuple), required=False, non_db=True,
            help='List containing the initial magnetization fer each site.')
        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.run_init,
            cls.run_dissociation,
            cls.inspect_results,
        )
        spec.output('curve_data', valid_type=orm.ArrayData,
            help='The computed total energy (and eventually spin) versus distance.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')

    def get_distances(self):
        """Return the list of scale factors."""
        if 'distances' in self.inputs:
            return self.inputs.distances

        count = self.inputs.distances_count.value
        maximum = self.inputs.distance_max.value
        minimum = self.inputs.distance_min.value
        return [orm.Float(minimum + i * (maximum-minimum) / (count-1)) for i in range(count)]

    def get_sub_workchain_builder(self, distance, previous_workchain=None):
        """Return the builder for the relax workchain."""
        molecule = set_distance(self.inputs.molecule, distance)
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        builder = process_class.get_inputs_generator().get_builder(
            molecule,
            previous_workchain=previous_workchain,
            **self.inputs.generator_inputs
        )
        builder._update(**self.inputs.get('sub_process', {}))  # pylint: disable=protected-access

        return builder

    def run_init(self):
        """Run the first workchain."""
        distance = self.get_distances()[0]
        builder = self.get_sub_workchain_builder(distance)
        self.report(f'submitting `{builder.process_class.__name__}` for distance `{distance.value}`')
        self.ctx.previous_workchain = self.submit(builder)
        self.to_context(children=append_(self.ctx.previous_workchain))

    def run_dissociation(self):
        """Run the sub process at each distance to compute the total energy."""
        for distance in self.get_distances()[1:]:
            previous_workchain = self.ctx.previous_workchain
            builder = self.get_sub_workchain_builder(distance, previous_workchain=previous_workchain)
            self.report(f'submitting `{builder.process_class.__name__}` for dinstance `{distance.value}`')
            self.to_context(children=append_(self.submit(builder)))

    def inspect_results(self):
        """
        Inspect all children workflows to make sure they finished successfully.
        Collect the total energies and return an array with the results.
        """
        if any([not child.is_finished_ok for child in self.ctx.children]):
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)  # pylint: disable=no-member

        self.report('distance (ang),  energy (eV)')

        collectwcinfo = {}
        for index, child in enumerate(self.ctx.children):
            dist = self.get_distances()[index].value
            collectwcinfo[f'd{dist}'.replace('.', '_')] = child.outputs.total_energy
            self.report(f'{self.get_distances()[index].value}, {child.outputs.total_energy.value}')

        self.out('curve_data', get_curve_data(**collectwcinfo))

@calcfunction
def get_curve_data(**energies):
    """
    Calcfunction that collects all the `total_energy` outputs
    nodes and creates an array energy versus distances.
    """
    distance = []
    energy = []
    for key, value in energies.items():
        dist = key.replace('_', '.')[1:]
        distance.append(float(dist))
        energy.append(value.value)

    import numpy as np
    array_data = np.array([distance, energy])
    curve_array = orm.ArrayData()
    curve_array.set_array('energy_vs_distance', array_data)
    return curve_array
