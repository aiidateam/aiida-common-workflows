# -*- coding: utf-8 -*-
"""
Workchain that wraps a CommonRelaxWorkChain and its input generator.
The challenge here is to transform the inputs accepted by the input generator
into Data nodes. This is required since they will be stored as inputs of a workchain.
Moreover this workchain is the central piece where to implement
the "overrides" system, meaning the possibility for experts of
a code to change the inputs of the relaxation.
"""
import inspect

from aiida import orm
from aiida.common import exceptions, AttributeDict
from aiida.engine import WorkChain, ToContext
from aiida.plugins import WorkflowFactory, DataFactory
from aiida.orm.nodes.data.base import to_aiida_type
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain
from aiida_common_workflows.workflows.relax.generator import CommonRelaxInputGenerator


def fix_valid_type(spec_inputs):
    """
    Transform the valid type of a spec().inputs from python type to
    the corresponding Data type. It also sets `to_aiida_type` as `serializer`
    so that the python types can still be passed as valid input.
    It is recursive so it fixes also namespaces.
    It ignores for the moment the "metadata" and the Enum.
    """
    from enum import Enum

    for port in spec_inputs:
        if port == 'metadata':
            continue

        if spec_inputs[port].valid_type is None:
            fix_valid_type(spec_inputs[port])
        elif issubclass(spec_inputs[port].valid_type, Enum):  #Waiting release aiida-core
            spec_inputs[port].non_db = True
        elif not issubclass(spec_inputs[port].valid_type, orm.Data):
            spec_inputs[port].valid_type = DataFactory(str(spec_inputs[port].valid_type)[8:-2])
            spec_inputs[port]._serializer = to_aiida_type  # pylint: disable=protected-access
            if spec_inputs[port].has_default():  #Surprised this is needed!
                spec_inputs[port].default = to_aiida_type(spec_inputs[port].default)


def deserialize(inputs):
    """
    Function used to deserialize the inputs of get_builder.

    In this workchain the inputs of `CommonRelaxInputGenerator`
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


def validate_inputs(value, _):  #pylint: disable=too-many-branches,too-many-return-statements
    """Validate the entire input namespace."""

    process_class = WorkflowFactory(value['relax_sub_process_class'].value)
    generator = process_class.get_input_generator()

    other_inputs = AttributeDict(value)
    other_inputs.pop('relax_sub_process_class')
    other_inputs.pop('metadata')
    other_inputs.pop('overrides', None)
    gen_inputs = deserialize(other_inputs)

    try:
        generator.get_builder(**gen_inputs)
    except Exception as exc:  # pylint: disable=broad-except
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `inputs`: {exc}'


def validate_sub_process_class(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value.value)
    except exceptions.EntryPointError:
        return f'`{value.value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonRelaxWorkChain):
        return f'`{value.value}` is not a subclass of the `CommonRelaxWorkChain` common workflow.'


class RelaxWorkChain(WorkChain):
    """
    Workchain to carry on a relaxation. The implementation to
    use is selected thanks to the `relax_sub_process_class` input,
    for the rest the interface is completely code-agnostic. It
    exposes the interface created to the input-generators system.
    """

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)

        spec.expose_inputs(CommonRelaxInputGenerator, exclude=('reference_workchain'))

        fix_valid_type(spec.inputs)

        spec.input('relax_sub_process_class',
            valid_type=orm.Str,
            serializer=to_aiida_type,
            validator=validate_sub_process_class
            )

        spec.input('overrides', non_db=True, required=False)

        spec.inputs.validator = validate_inputs

        spec.outline(cls.run_wc, cls.analyze_wc)

        spec.output('relaxed_structure', valid_type=orm.StructureData, required=False,
            help='All cell dimensions and atomic positions are in Ångstrom.')
        spec.output('forces', valid_type=orm.ArrayData, required=False,
            help='The final forces on all atoms in eV/Å.')
        spec.output('stress', valid_type=orm.ArrayData, required=False,
            help='The final stress tensor in eV/Å^3.')
        spec.output('trajectory', valid_type=orm.TrajectoryData, required=False,
            help='All cell dimensions and atomic positions are in Ångstrom.')
        spec.output('total_energy', valid_type=orm.Float, required=False,
            help='Total energy in eV.')
        spec.output('total_magnetization', valid_type=orm.Float, required=False,
            help='Total magnetization in Bohr magnetons.')
        spec.output('remote_folder', valid_type=orm.RemoteData, required=False,
            help='Folder of the last run calculation.')

        #Exposing the outputs does not work, probably because CommonRelaxWorkChain
        #is an abstract class.
        #spec.expose_outputs(CommonRelaxWorkChain)

        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the sub processes did not finish successfully.')


    def run_wc(self):
        """
        Run the relaxation workchain.
        """
        process_class = WorkflowFactory(self.inputs.relax_sub_process_class.value)

        all_inputs = AttributeDict(self.inputs)
        all_inputs.pop('relax_sub_process_class')
        all_inputs.pop('metadata')
        all_inputs.pop('overrides', None)
        inputs_for_builder = deserialize(all_inputs)

        builder = process_class.get_input_generator().get_builder(
            **inputs_for_builder
        )
        #builder._update(**self.inputs.get('relax_sub_process', {}))  # pylint: disable=protected-access

        #self.report(f'{builder}')

        #Apply code dependent overrides
        if 'overrides' in self.inputs:
            for idx, override_func in enumerate(self.inputs['overrides']['functions']):
                override_func(builder, **self.inputs['overrides']['params'][idx])

        #self.report(f'{builder}')

        self.report(f'submitting `{builder.process_class.__name__}` for relaxation.')

        return ToContext(workchain_relax=self.submit(builder))

    def analyze_wc(self):
        """
        Check the success of the relax calculation and return outputs.
        """
        self.report('Workchain concluded')

        if not self.ctx.workchain_relax.is_finished_ok:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        self.report('Workchain succesfull, returning outputs')

        for out in self.ctx.workchain_relax.outputs:
            self.out(out, self.ctx.workchain_relax.outputs[out])

        return None
