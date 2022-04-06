# -*- coding: utf-8 -*-
"""
Workflow that runs a relaxation and subsequently calculates bands.

It can use any code plugin implementing the common relax workflow and the
common bands workflow.
It also allows the automatic use of ``seekpath`` in order to get the high
symmetries path for bands.
"""
from functools import partial
import inspect

from aiida import orm
from aiida.common import AttributeDict, exceptions
from aiida.engine import ToContext, WorkChain, calcfunction, if_
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.common import RelaxType
from aiida_common_workflows.workflows.bands.generator import CommonBandsInputGenerator
from aiida_common_workflows.workflows.bands.workchain import CommonBandsWorkChain
from aiida_common_workflows.workflows.relax.generator import CommonRelaxInputGenerator
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


@calcfunction
def seekpath_explicit_kp_path(structure, **seekpath_params):
    """
    Return the modified structure of SeekPath and the explicit list of kpoints.

    :param structure: StructureData containing the structure information.
    :param seekpath_params: Dict of seekpath parameters to be unwrapped as arguments of `get_explicit_kpoints_path`.
    """
    from aiida.tools import get_explicit_kpoints_path

    results = get_explicit_kpoints_path(structure, **seekpath_params)

    return {'structure': results['primitive_structure'], 'kpoints': results['explicit_kpoints']}


def validate_inputs(value, _):  #pylint: disable=too-many-branches,too-many-return-statements
    """Validate the entire input namespace."""

    process_class = WorkflowFactory(value['relax_sub_process_class'].value)
    generator = process_class.get_input_generator()

    # Validate that the provided ``relax`` inputs are valid for the associated input generator.
    try:
        generator.get_builder(**AttributeDict(value['relax']))
    except Exception as exc:  # pylint: disable=broad-except
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `relax_inputs`: {exc}'

    # Raise when a relax type with variable cell is selected and also the the kpoints for bands
    # are specified in input.
    if 'bands_kpoints' in value['bands']:
        if value['relax']['relax_type'] not in [RelaxType.NONE, RelaxType.POSITIONS]:
            message = (
                'A kpoints path for bands in input is incompatible with a `relax_type` that ' +
                'involves cell modification.'
            )
            return message

    # Validate that the plugin for bands and the relax are the same
    bands_plugin = value['bands_sub_process_class'].value.replace('common_workflows.bands.', '')
    relax_plugin = value['relax_sub_process_class'].value.replace('common_workflows.relax.', '')
    if relax_plugin != bands_plugin:
        return 'Different code between relax and bands. Not supported yet.'


def validate_sub_process_class(value, _, required_class=None):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value.value)
    except exceptions.EntryPointError:
        return f'`{value.value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, required_class):
        return f'`{value.value}` is not a subclass of the `{required_class}` common workflow.'


class RelaxAndBandsWorkChain(WorkChain):
    """
    Workflow to carry on a relaxation and subsequently calculate the bands.

    It allows three possibilities:
    1) relax+seekpath+scf+bands, when ``bands.bands_kpoints`` is NOT in input
    2) relax+kp_in_input+bands, when ``bands.bands_kpoints`` is in input
    3) relax+kp_in_input+scf+bands, when ``bands.bands_kpoints`` is in input AND ``extra_scf``
       namespace is populated
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
            valid_type=orm.Float,
            default=lambda: orm.Float(0.025),
            serializer=to_aiida_type,
            help='Reference target distance between neighboring k-points along the path in units 1/Å.',
        )
        spec.input(
            'seekpath_parameters.symprec',
            valid_type=orm.Float,
            default=lambda: orm.Float(0.00001),
            serializer=to_aiida_type,
            help='The symmetry precision used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.angle_tolerance',
            valid_type=orm.Float,
            default=lambda: orm.Float(-1.0),
            serializer=to_aiida_type,
            help='The angle tollerance used internally by SPGLIB.',
        )
        spec.input(
            'seekpath_parameters.threshold',
            valid_type=orm.Float,
            default=lambda: orm.Float(0.0000001),
            serializer=to_aiida_type,
            help='The treshold for determining edge cases. Meaning is different depending on bravais lattice.',
        )
        spec.input(
            'seekpath_parameters.with_time_reversal',
            valid_type=orm.Bool,
            default=lambda: orm.Bool(True),
            serializer=to_aiida_type,
            help='If False, and the group has no inversion symmetry, additional lines are returned.',
        )

        spec.expose_inputs(
                CommonRelaxInputGenerator,
                namespace='relax',
                namespace_options={'help':'inputs for the relaxation, they are inputs of CommonRelaxInputGenerator'}
                )
        spec.inputs['relax']['protocol'].non_db = True
        spec.inputs['relax']['spin_type'].non_db = True
        spec.inputs['relax']['relax_type'].non_db = True
        spec.inputs['relax']['electronic_type'].non_db = True
        spec.inputs['relax']['magnetization_per_site'].non_db = True
        spec.inputs['relax']['threshold_forces'].non_db = True
        spec.inputs['relax']['threshold_stress'].non_db = True
        spec.inputs['relax']['engines']['relax']['options'].non_db = True

        spec.expose_inputs(
                CommonBandsInputGenerator,
                namespace='bands',
                exclude=('parent_folder'),
                namespace_options={'help':'inputs for the bands calc, they are inputs of CommonBandsInputGenerator'}
                )
        spec.inputs['bands']['engines']['bands']['options'].non_db = True
        spec.inputs['bands']['bands_kpoints'].required = False

        spec.expose_inputs(
                CommonRelaxInputGenerator,
                namespace='extra_scf',
                exclude=('structure', 'relax_type', 'threshold_stress', 'threshold_forces'),
                namespace_options={
                    'required': False,
                    'populate_defaults': False,
                    'help': 'inputs of a possible second relaxation, if not specified, '
                        'inputs of first relaxation will be used, except the relaxation type set to NONE'
                        }
                )
        spec.inputs['extra_scf']['protocol'].non_db = True
        spec.inputs['extra_scf']['protocol'].default = ()
        spec.inputs['extra_scf']['spin_type'].non_db = True
        spec.inputs['extra_scf']['spin_type'].default = ()
        spec.inputs['extra_scf']['electronic_type'].non_db = True
        spec.inputs['extra_scf']['magnetization_per_site'].non_db = True
        spec.inputs['extra_scf']['engines']['relax']['options'].non_db = True
        spec.inputs['extra_scf']['engines']['relax']['code'].required = False

        spec.input('relax_sub_process_class',
                valid_type=orm.Str,
                serializer=to_aiida_type,
                validator=partial(validate_sub_process_class, required_class=CommonRelaxWorkChain)
                )
        spec.input('bands_sub_process_class',
                valid_type=orm.Str,
                serializer=to_aiida_type,
                validator=partial(validate_sub_process_class, required_class=CommonBandsWorkChain)
                )

        spec.inputs.validator = validate_inputs

        spec.outline(
            cls.initialize,
            cls.run_common_relax_wc,
            cls.inspect_common_relax_wc,
            if_(cls.should_use_seekpath)(
                cls.fix_structure,
                cls.use_seekpath,
                cls.fix_inputs,
                cls.run_common_relax_wc,
                cls.inspect_common_relax_wc
            ).elif_(cls.extra_scf_requested)(
                cls.fix_structure,
                cls.fix_inputs,
                cls.run_common_relax_wc,
                cls.inspect_common_relax_wc
            ),
            cls.run_bands,
            cls.inspect_bands
        )

        spec.output('structure', valid_type=orm.StructureData, help='The final structure.')
        spec.output('bands', valid_type=orm.BandsData,
            help='The computed total energy of the relaxed structures at each scaling factor.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the sub processes did not finish successfully.')


    def initialize(self):
        """
        Initialize some variables that will be used and modified in the workchain.
        """
        self.ctx.inputs = AttributeDict(self.inputs.relax)
        self.ctx.need_other_scf = False


    def run_common_relax_wc(self):
        """
        Run the common relax workchain.

        It can be a relaxation or a simple scf, depending on the ``self.ctx.inputs``.
        """
        process_class = WorkflowFactory(self.inputs.relax_sub_process_class.value)

        builder = process_class.get_input_generator().get_builder(
            **self.ctx.inputs
        )
        #builder._update(**self.inputs.get('relax_sub_process', {}))  # pylint: disable=protected-access

        self.report(f'submitting `{builder.process_class.__name__}` for relaxation.')
        running = self.submit(builder)

        return ToContext(workchain_relax=running)


    def inspect_common_relax_wc(self):
        """
        Check that the first relax workchain finished successfully.

        Otherwise abort the workchain.
        """
        if not self.ctx.workchain_relax.is_finished_ok:
            self.report('Relaxation did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.relax_sub_process_class.value)  # pylint: disable=no-member


    def should_use_seekpath(self):
        """
        Bool that triggers the use of SeeK-path

        Any time ``bands.bands_kpoints`` is not in input, SeeKpath is called.
        """
        return 'bands_kpoints' not in self.inputs.bands


    def fix_structure(self):
        """
        Set the structure to the output structure of a previously run relaxation.

        It is called before calling the second ``run_common_relax_wc``.
        """
        if 'relaxed_structure' in self.ctx.workchain_relax.outputs:
            self.ctx.inputs['structure'] = self.ctx.workchain_relax.outputs.relaxed_structure


    def use_seekpath(self):
        """
        Use SeeK-path to get the high symmetry path for the calculation of bands.

        It might change the structure to a conventional one.
        """
        self.report('Using SekPath to create kpoints for bands. Structure might change.')
        seekpath_dict = AttributeDict(self.inputs.seekpath_parameters)
        res = seekpath_explicit_kp_path(self.ctx.inputs['structure'], **seekpath_dict)
        self.ctx.inputs['structure'] = res['structure']
        self.ctx.bandskpoints = res['kpoints']
        #self.ctx.need_other_scf = True


    def fix_inputs(self):
        """
        Set the inputs for a possible extra scf step.

        Set the inputs of a possible second call to the CommonRelaxInputGenerator.
        This includes forcing ``RelaxType`` to be ``NONE`` and adding whatever optional overrides
        specified by users in the ``extra_scf`` namespace.
        """
        self.ctx.inputs['relax_type'] = RelaxType.NONE

        if 'extra_scf' in self.inputs:
            for key in self.ctx.inputs:
                if key == 'engines':
                    if 'code' in self.inputs.extra_scf[key]['relax']:
                        self.ctx.inputs[key]['relax']['code'] = self.inputs.extra_scf[key]['relax']['code']
                    if 'options' in self.inputs.extra_scf[key]['relax']:
                        self.ctx.inputs[key]['relax']['options'] = self.inputs.extra_scf[key]['relax']['options']
                    continue
                if key in self.inputs.extra_scf:
                    self.ctx.inputs[key] = self.inputs.extra_scf[key]

        self.report('Set the inputs of the extra scf step')


    def extra_scf_requested(self):
        """
        Bool that returns wheather a scf is requested by user.

        This is done populating ant port of the ``extra_scf`` namespace.
        """
        if 'extra_scf' in self.inputs:
            self.report('A new scf run requested')

        return 'extra_scf' in self.inputs


    def run_bands(self):
        """
        Run the sub process to obtain the bands.
        """
        rel_wc = self.ctx.workchain_relax

        if not self.should_use_seekpath():
            self.ctx.bandskpoints = self.inputs.bands['bands_kpoints']

        process_class = WorkflowFactory(self.inputs.bands_sub_process_class.value)

        builder = process_class.get_input_generator().get_builder(
            bands_kpoints=self.ctx.bandskpoints,
            parent_folder=rel_wc.outputs.remote_folder,
            engines=AttributeDict(self.inputs.bands['engines']),
        )

        #builder._update(**self.inputs.get('bands_sub_process', {}))  # pylint: disable=protected-access

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

        self.report('Bands calculation finished successfully, returning outputs')

        self.out('structure', self.ctx.workchain_bands.inputs.structure)
        self.out('bands', self.ctx.workchain_bands.outputs.bands)
