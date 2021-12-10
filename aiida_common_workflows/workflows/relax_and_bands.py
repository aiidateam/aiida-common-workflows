# -*- coding: utf-8 -*-
"""
Workflow that runs a relaxation and subsequently calculates bands.
It can use any code plugin implementing the common relax workflow and the
common bands workflow. It also allows the relaxation with one code and the
bands calculations with another.
It also allows the automatic use of `seekpath` in order to get the high
symmetries path for bands.
"""
import inspect

from aiida import orm
from aiida.common import AttributeDict, NotExistent, exceptions
from aiida.engine import ToContext, WorkChain, calcfunction, if_
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.bands.generator import CommonBandsInputGenerator
from aiida_common_workflows.workflows.bands.workchain import CommonBandsWorkChain
from aiida_common_workflows.workflows.relax.generator import CommonRelaxInputGenerator, RelaxType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def deserialize(inputs):
    """
    Function used to deserialize the inputs of get_builder. It also removes some specific
    inputs that are not wanted.

    In this workchain the inputs of `CommonRelaxInputGenerator` and `CommonBandsInputGenerator`
    are exposed to the users of the workchain. However, in order to have them exposed,
    it is necessary to transform them in aiida data type. This is done by various commands in
    the `define` method of this workchain.
    However, then these inputs need to be passed to the `get_builder`, that accepts normal python
    types and not AiiDA data types. Here we deserialize the inputs to bring
    them to normal python types.
    """

    for key, val in inputs.items():
        if isinstance(val, (orm.Float, orm.Str, orm.Int, orm.Bool)):
            inputs[key] = val.value
        if isinstance(val, orm.Dict):
            inputs[key] = val.get_dict()
        if isinstance(val, orm.List):
            inputs[key] = val.get_list()
        if isinstance(val, orm.Code):
            inputs[key] = val.label
        if isinstance(val, dict):
            deserialize(val)

    return inputs


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


def validate_inputs(value, _):  #pylint: disable=too-many-branches,too-many-return-statements
    """Validate the entire input namespace."""

    process_class = WorkflowFactory(value['relax_sub_process_class'].value)
    generator = process_class.get_input_generator()

    # Validate that the provided ``relax_inputs`` are valid for the associated input generator.
    try:
        generator.get_builder(**deserialize(AttributeDict(value['relax_inputs'])))
    except Exception as exc:  # pylint: disable=broad-except
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `relax_inputs`: {exc}'

    #process_class_bands = WorkflowFactory(value['bands_sub_process_class'].value)
    #generator_bands = process_class_bands.get_input_generator()

    #first_relax_plugin = value['relax_sub_process_class'].replace('common_workflows.relax.', '')
    #bands_plugin = value['bands_sub_process_class'].replace('common_workflows.bands.', '')
    #if first_relax_plugin != bands_plugin:
    #    return 'Different code between relax and bands. Not supported yet.'


def validate_sub_process_class_r(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value.value)
    except exceptions.EntryPointError:
        return f'`{value.value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonRelaxWorkChain):
        return f'`{value.value}` is not a subclass of the `CommonRelaxWorkChain` common workflow.'


def validate_sub_process_class_b(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value.value)
    except exceptions.EntryPointError:
        return f'`{value.value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonBandsWorkChain):
        return f'`{value.value}` is not a subclass of the `CommonBandsWorkChain` common workflow.'


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

        namspac = spec.inputs.create_port_namespace('relax_inputs')
        namspac.absorb(CommonRelaxInputGenerator.spec().inputs)
        namspac['protocol'].non_db = True
        namspac['spin_type'].non_db = True
        namspac['relax_type'].non_db = True
        namspac['electronic_type'].non_db = True
        namspac['magnetization_per_site'].non_db = True
        namspac['threshold_forces'].non_db = True
        namspac['threshold_stress'].non_db = True
        namspac['engines']['relax']['options'].non_db = True

        namspac2 = spec.inputs.create_port_namespace('bands_inputs')
        namspac2.absorb(CommonBandsInputGenerator.spec().inputs, exclude=('parent_folder'))
        namspac2['engines']['bands']['options'].non_db = True
        namspac2['bands_kpoints'].required = False

        namspac3 = spec.inputs.create_port_namespace('second_relax_inputs')
        namspac3.absorb(CommonRelaxInputGenerator.spec().inputs, exclude=('structure'))
        namspac3['protocol'].non_db = True
        namspac3['spin_type'].non_db = True
        namspac3['relax_type'].non_db = True
        namspac3['electronic_type'].non_db = True
        namspac3['magnetization_per_site'].non_db = True
        namspac3['threshold_forces'].non_db = True
        namspac3['threshold_stress'].non_db = True
        namspac3['engines']['relax']['options'].non_db = True
        for key in namspac3:
            namspac3[key].required = False
            namspac3[key].populate_defaults = False
        namspac3['relax_type'].required = True
        namspac3['relax_type'].default = RelaxType.NONE

        spec.input('relax_sub_process_class', 
                valid_type=orm.Str, 
                serializer=to_aiida_type,
                validator=validate_sub_process_class_r
                )
        spec.input('bands_sub_process_class',
                valid_type=orm.Str,
                serializer=to_aiida_type,
                validator=validate_sub_process_class_b
                )

        spec.inputs.validator = validate_inputs

        spec.outline(
            cls.initialize,
            cls.run_relax,
            cls.prepare_bands,
            if_(cls.should_run_other_scf)(
                cls.fix_inputs,
                cls.run_relax
            ),
            cls.run_bands,
            cls.inspect_bands
        )

        spec.output('final_structure', valid_type=orm.StructureData, help='The final structure.')
        spec.output('bands', valid_type=orm.BandsData,
            help='The computed total energy of the relaxed structures at each scaling factor.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the sub processes did not finish successfully.')


    def initialize(self):
        """
        Initialize some variables that will be used and modified in the workchain
        """
        self.ctx.inputs = AttributeDict(self.inputs.relax_inputs)
        self.ctx.need_other_scf = False

    def run_relax(self):
        """
        Run the relaxation workchain.
        """
        process_class = WorkflowFactory(self.inputs.relax_sub_process_class.value)

        self.report(self.ctx.inputs)

        builder = process_class.get_input_generator().get_builder(
            **self.ctx.inputs
        )
        #builder._update(**self.inputs.get('relax_sub_process', {}))  # pylint: disable=protected-access

        self.report(f'submitting `{builder.process_class.__name__}` for relaxation.')
        running = self.submit(builder)

        return ToContext(workchain_relax=running)


    def prepare_bands(self):
        """
        Check that the first workchain finished successfully or abort the workchain.
        """
        if not self.ctx.workchain_relax.is_finished_ok:
            self.report('Relaxation did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.relax_sub_process_class.value)  # pylint: disable=no-member
        if 'relaxed_structure' in self.ctx.workchain_relax.outputs:
            structure = self.ctx.workchain_relax.outputs.relaxed_structure
        else:
            structure = self.ctx.inputs['structure']

        #self.report(self.inputs.second_relax_inputs)
        if 'bands_kpoints' not in self.inputs.bands_inputs:
            self.report('Using SekPath to create kpoints for bands. Structure might change.')
            seekpath_dict_to_aiida = orm.Dict(dict=deserialize(AttributeDict(self.inputs.seekpath_parameters)))
            res = seekpath_explicit_kp_path(structure, seekpath_dict_to_aiida)
            self.ctx.inputs['structure'] = res['structure']
            self.ctx.bandskpoints = res['kpoints']
            self.ctx.need_other_scf = True
        else:
            self.report('Kpoints for bands in inputs detected.')
            self.ctx.need_other_scf = False
            self.ctx.bandskpoints = self.inputs.bands_inputs['bands_kpoints']

        if self.ctx.need_other_scf:
            self.report('A new scf cycle needed')

    def should_run_other_scf(self):
        """
        Return the bool variable that triggers a further scf calculation before the bands run.
        """
        return self.ctx.need_other_scf

    def fix_inputs(self):
        """
        Add to the inputs of the second relaxation whatever optional overrides
        specified by users in `second_relax_inputs` namespace.
        """
        for key in self.ctx.inputs:
            if key in self.inputs.second_relax_inputs:
                self.ctx.inputs[key] = self.inputs.second_relax_inputs[key]


    def run_bands(self):
        """
        Run the sub process to obtain the bands.
        """
        rel_wc = self.ctx.workchain_relax

        process_class = WorkflowFactory(self.inputs.bands_sub_process_class.value)

        #bands_inpus_no_kp = AttributeDict(self.inputs.bands_inputs)
        #if "bands_kpoints" in bands_inpus_no_kp:
        #    bands_inpus_no_kp.pop("bands_kpoints")

        #self.report(bands_inpus_no_kp)

        builder = process_class.get_input_generator().get_builder(
            bands_kpoints=self.ctx.bandskpoints,
            parent_folder=rel_wc.outputs.remote_folder,
            engines = self.inputs.bands_inputs["engines"],
            #**bands_inpus_no_kp
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

        self.out('final_structure', self.ctx.workchain_bands.inputs.structure)
        self.out('bands', self.ctx.workchain_bands.outputs.bands)
