# -*- coding: utf-8 -*-
"""Equation of state workflow that can use any code plugin implementing the common relax workflow."""
import inspect

from aiida import orm
from aiida.common import exceptions, AttributeDict
from aiida.engine import WorkChain, if_, calcfunction, ToContext
from aiida.plugins import WorkflowFactory, DataFactory

from aiida_common_workflows.workflows.relax.generator import RelaxType, SpinType, ElectronicType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain
from aiida_common_workflows.workflows.bands.workchain import CommonBandsWorkChain


@calcfunction
def seekpath_explicit_kp_path(structure, seekpath_params):
    """
    Return the modified structure of SeekPath and the explicit list of kpoints.
    :param structure: StructureData containing the structure information.
    :param seekpath_params: Dict of seekpath parameters to be unwrapped as arguments of `get_explicit_kpoints_path`.
    """
    from aiida.tools import get_explicit_kpoints_path

    results = get_explicit_kpoints_path(structure, **seekpath_params)

    return {'structure': results['primitive_structure'], 'kpoints': results['explicit_kpoints']}


def validate_inputs(value, _):
    """Validate the entire input namespace."""

    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['relax_sub_process_class'])
    generator = process_class.get_input_generator()

    try:
        generator.get_builder(structure=value['structure'], **value['relax_inputs'])
    except Exception as exc:  # pylint: disable=broad-except
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `generator_inputs`: {exc}'

    #Validate engines of bands


def validate_sub_process_class_r(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value)
    except exceptions.EntryPointError:
        return f'`{value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonRelaxWorkChain):
        return f'`{value}` is not a subclass of the `CommonRelaxWorkChain` common workflow.'


def validate_sub_process_class_b(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value)
    except exceptions.EntryPointError:
        return f'`{value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonBandsWorkChain):
        return f'`{value}` is not a subclass of the `CommonBandsWorkChain` common workflow.'


class RelaxAndBandsWorkChain(WorkChain):
    """
    Workflow to carry on a relaxation and subsequently calculate the bands.
    """

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input_namespace(
            'seekpath_parameters',
            help='Inputs for the seekpath to be passed to `get_explicit_kpoints_path`.',
        )
        spec.input(
            'seekpath_parameters.reference_distance',
            valid_type=float,
            default=0.025,
            non_db=True,
            help='Reference target distance between neighboring k-points along the path in units 1/Å.',
        )
        spec.input(
            'seekpath_parameters.symprec',
            valid_type=float,
            default=0.00001,
            non_db=True,
            help='The symmetry precision used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.angle_tolerance',
            valid_type=float,
            default=-1.0,
            non_db=True,
            help='The angle tollerance used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.threshold',
            valid_type=float,
            default=0.0000001,
            non_db=True,
            help='The treshold for determining edge cases. Meaning is different depending on bravais lattice.',
        )
        spec.input(
            'seekpath_parameters.with_time_reversal',
            valid_type=bool,
            default=True,
            non_db=True,
            help='If False, and the group has no inversion symmetry, additional lines are returned.',
        )
        spec.input(
            'bands_kpoints',
            valid_type=DataFactory('array.kpoints'),
            required=False,
            help='The full list of kpoints where to calculate bands, in (direct) coordinates of the reciprocal space.'
        )
        spec.input('structure', valid_type=orm.StructureData, help='The structure might be change by seekpath!')
        spec.input_namespace('relax_inputs',
            help='The inputs that will be passed to the input generator of a `CommonRelaxWorkChain`.')
        spec.input('relax_inputs.engines', valid_type=dict, non_db=True)
        spec.input('relax_inputs.protocol', valid_type=str, non_db=True,
            help='The protocol to use when determining the workchain inputs.')
        spec.input('relax_inputs.relax_type', valid_type=(RelaxType, str), non_db=True,
            help='The type of relaxation to perform.')
        spec.input('relax_inputs.spin_type', valid_type=(SpinType, str), required=False, non_db=True,
            help='The type of spin for the calculation.')
        spec.input('relax_inputs.electronic_type', valid_type=(ElectronicType, str), required=False, non_db=True,
            help='The type of electronics (insulator/metal) for the calculation.')
        spec.input('relax_inputs.magnetization_per_site', valid_type=(list, tuple), required=False, non_db=True,
            help='List containing the initial magnetization per atomic site.')
        spec.input('relax_inputs.threshold_forces', valid_type=float, required=False, non_db=True,
            help='Target threshold for the forces in eV/Å.')
        spec.input('relax_inputs.threshold_stress', valid_type=float, required=False, non_db=True,
            help='Target threshold for the stress in eV/Å^3.')
        spec.input_namespace('bands_inputs', required=False,
            help='The inputs that will be passed to the input generator of a `CommonBandsWorkChain`.')
        spec.input('bands_inputs.engines', valid_type=dict, non_db=True, required=False)
        spec.input_namespace('relax_sub_process', dynamic=True, populate_defaults=False)
        spec.input_namespace('bands_sub_process', dynamic=True, populate_defaults=False)
        spec.input('relax_sub_process_class', non_db=True, validator=validate_sub_process_class_r)
        spec.input('bands_sub_process_class', non_db=True, validator=validate_sub_process_class_b)
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.initialize,
            cls.run_relax,
            cls.prepare_bands,
            if_(cls.should_run_other_scf)(
                cls.run_relax
            ),
            cls.run_bands,
            cls.inspect_bands,
        )
        spec.output('final_structure', valid_type=orm.StructureData, help='The final structure.')
        spec.output('bands', valid_type=orm.BandsData,
            help='The computed total energy of the relaxed structures at each scaling factor.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')


    def initialize(self):
        """
        Initialize some variables that will be used and modified in the workchain
        """
        self.ctx.structure = self.inputs.structure
        self.ctx.need_other_scf = False

    def run_relax(self):
        """
        Run the relaxation workchain.
        """
        structure = self.ctx.structure
        process_class = WorkflowFactory(self.inputs.relax_sub_process_class)

        inputs_gen = AttributeDict(self.inputs.relax_inputs)

        # Impose RelaxType.NONE when the relax workcain is called the second time
        if self.ctx.need_other_scf:
            inputs_gen['relax_type'] = RelaxType.NONE

        builder = process_class.get_input_generator().get_builder(
            structure=structure,
            **inputs_gen
        )
        builder._update(**self.inputs.get('relax_sub_process', {}))  # pylint: disable=protected-access

        self.report(f'submitting `{builder.process_class.__name__}` for relaxation.')
        running = self.submit(builder)

        return ToContext(workchain_relax=running)

    def prepare_bands(self):
        """
        Check that the first workchain finished successfully or abort the workchain.
        Then anal
        """
        if not self.ctx.workchain_relax.is_finished_ok:
            self.report('Relaxation did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.relax_sub_process_class)  # pylint: disable=no-member
        if 'relaxed_structure' in self.ctx.workchain_relax.outputs:
            structure = self.ctx.workchain_relax.outputs.relaxed_structure
        else:
            structure = self.inputs.structure

        if 'bands_kpoints' not in self.inputs:
            self.report('Using SekPath to create kpoints for bands. Structure might change. A new scf cycle needed')
            res = seekpath_explicit_kp_path(structure, orm.Dict(dict=self.inputs.seekpath_parameters))
            self.ctx.structure = res['structure']
            self.ctx.bandskpoints = res['kpoints']
            self.ctx.need_other_scf = True
        else:
            self.report('Kpoints for bands in inputs detected.')
            self.ctx.need_other_scf = False
            self.ctx.bandskpoints = self.inputs.bands_kpoints
            self.ctx.structure = structure

    def should_run_other_scf(self):
        """
        Return the bool variable that triggers a further scf calculation before the bands run.
        """
        return self.ctx.need_other_scf

    def run_bands(self):
        """
        Run the sub process to obtain the bands.
        """
        process_class = WorkflowFactory(self.inputs.bands_sub_process_class)

        builder = process_class.get_input_generator().get_builder(
            bands_kpoints=self.ctx.bandskpoints,
            parent_folder=self.ctx.workchain_relax.outputs.remote_folder,
            **self.inputs.bands_inputs
        )

        builder._update(**self.inputs.get('bands_sub_process', {}))  # pylint: disable=protected-access

        self.report(f'submitting `{builder.process_class.__name__}` for bands.')
        running = self.submit(builder)

        return ToContext(workchain_bands=running)

    def inspect_bands(self):
        """
        Check the success of the bands calculation and return outputs.
        """
        if not self.ctx.workchain_bands.is_finished_ok:
            self.report('Bands calculation did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.bands_sub_process_class)

        self.out('final_structure', self.ctx.workchain_bands.inputs.structure)
        self.out('bands', self.ctx.workchain_bands.outputs.bands)
