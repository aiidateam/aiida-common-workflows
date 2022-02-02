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
from aiida.common import AttributeDict, exceptions
from aiida.engine import ToContext, WorkChain
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.plugins import DataFactory, WorkflowFactory
from importlib_metadata import entry_points

from aiida_common_workflows.workflows.relax.generator import CommonRelaxInputGenerator
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain


def validate_overrides(value, _):  #pylint: disable=too-many-return-statements
    """
    Validate the overrides input port
    """
    found_group = entry_points().select(group='acwf.overrides')
    if not found_group:  #an empty list is returned if no group found
        return 'No group `acwf.overrides` found among entry points. Maybe reinstall the package?'

    for over in value.get_list():
        if not isinstance(over, dict):
            return 'The `overrides` input must contain a list of dictionaries'
        if 'entrypoint' not in over:
            return 'Each override dictionary must contain the keyword `entrypoint`'
        found = entry_points().select(group='acwf.overrides', name=over['entrypoint'])
        if not found:  #an empty list is returned if no name found
            return f"{over['entrypoint']} is not a registered entry point"
        if len(found.names) > 1:
            return f"more than one entry point with name {over['entrypoint']} found. Fix the `setup.json`."
        if 'kwargs' not in over:
            return 'Each override dictionary must contain the keyword `kwargs`'
        if not isinstance(over['kwargs'], dict):
            return 'The `kwargs` of every `overrides` must be a dictionary'


def recursive_serialize_kwargs(diction):
    """
    Serialize a dictionary according to the rule
    that every orm.Node is transformed into its uuid
    """
    for obj_k, obj_v in diction.items():
        if isinstance(obj_v, dict):
            diction[obj_k] = recursive_serialize_kwargs(obj_v)
        if isinstance(obj_v, orm.Node):
            if not obj_v.is_stored:
                obj_v.store()
            diction[obj_k] = obj_v.uuid

    return diction


def serialize_overrides(value):
    '''
    Serialize the `overrides` port. In particular trsformes orm.Node into its uuid.
    This is done because aiida's List does not accept Nodes as items, nor as
    components of items.
    :param overrides: the content passed to the overrides input port (a orm.List).
    :return: an aiida List containing the uuid of each element of list_to_parse
    '''
    for over in value:
        over['kwargs'] = recursive_serialize_kwargs(over['kwargs'])

    return orm.List(list=value)


def find_common_rel_wc(work_chain):
    """
    Recursively goes through the callers of a workchain
    and looks for subclasses of `CommonRelaxWorkChain`.
    """
    if issubclass(work_chain.process_class, CommonRelaxWorkChain):
        return work_chain

    if work_chain.caller is not None:
        find_common_rel_wc(work_chain.caller)
    else:
        return None


def validate_reference_wc_remote_folder(value, _):
    """
    validate the port `reference_wc_remote_folder`, making
    sure that was returned by a subclass of `CommonRelaxWorkChain`.
    """
    creator = value.creator

    ref_wc = find_common_rel_wc(creator.caller)

    if ref_wc is None:
        return 'the `reference_wc_remote_folder` is not connected to any implementation of `CommonRelaxWorkChain`'


def from_remote_folder_to_reference_wc(folder):
    """
    Returns the instance of `CommonRelaxWorkChain` (or subclasses)
    that returned the `folder` (`RemoteData`)
    """
    creator = folder.creator

    return find_common_rel_wc(creator.caller)


def fix_valid_type(spec_inputs):
    """
    Transform the valid type of a spec().inputs from python type to
    the corresponding Data type. It also sets `to_aiida_type` as `serializer`
    so that the python types can still be passed as valid inputs.
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

    if 'reference_wc_remote_folder' in value:
        ref_wc = from_remote_folder_to_reference_wc(value['reference_wc_remote_folder'])
        if ref_wc is None:
            return 'The provided `reference_wc_remote_folder` is not connected to any CommonRelaxInputGenerator'
        other_inputs['reference_workchain'] = ref_wc
        other_inputs.pop('reference_wc_remote_folder')

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
        #Note that we expose the inputs of the abstract class `CommonRelaxInputGenerator`.
        #This has the limitation to not record possible changes in the `spec`
        #introduced in the subclasses of `CommonRelaxInputGenerator` (i.e.
        #the various code implementations - `<Code>CommonRelaxInputGenerator`).
        #A consequence is that the inspection of the `valid_type` and allowed values
        #for an input might be misleading since a feature that is present for the abstract
        #class might have been removed for a particular implementation.
        #The definition of an invalid value will be anyway catch at the validation level
        #where we verify the inputs against the correct implementation.
        #A way bigger problem is faced when new features are implemeted in the
        #`<Code>CommonRelaxInputGenerator`. This includes new input ports, but also
        #new valid choices for some ports. This would not be accessible in the current.
        #implementation. The introduction of new features in the
        #`<Code>CommonRelaxInputGenerator` is therefore totally discourage.
        #The `reference_workchain` is `WorkChainNode` and this type of Node are not
        #allowed as inputs of a WorkChain. A workaround is implemented:
        #set the `remote_folder` output of `CommonRelaxWorkChain` as input here.
        #We then implement the logic to go from the `remote_folder` to the associated
        #`CommonRelaxWorkChain`. The latter will be passed as `reference_workchain` to the input generator.

        fix_valid_type(spec.inputs)

        spec.input('reference_wc_remote_folder',
            valid_type=orm.RemoteData,
            required=False,
            validator=validate_reference_wc_remote_folder
            )

        spec.input('relax_sub_process_class',
            valid_type=orm.Str,
            serializer=to_aiida_type,
            validator=validate_sub_process_class
            )

        spec.input(
            'overrides',
            valid_type=orm.List,
            required=False,
            serializer=serialize_overrides,
            validator=validate_overrides
            )

        spec.inputs.validator = validate_inputs

        spec.outline(cls.run_wc, cls.analyze_wc)

        spec.expose_outputs(CommonRelaxWorkChain)
        spec.outputs.dynamic = True

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

        if 'reference_wc_remote_folder' in all_inputs:
            ref_wc = from_remote_folder_to_reference_wc(all_inputs['reference_wc_remote_folder'])
            all_inputs['reference_workchain'] = ref_wc
            all_inputs.pop('reference_wc_remote_folder')

        inputs_for_builder = deserialize(all_inputs)

        builder = process_class.get_input_generator().get_builder(
            **inputs_for_builder
        )

        #Apply code dependent overrides
        if 'overrides' in self.inputs:
            self.report('Applying overrides')
            for over in self.inputs['overrides']:
                found = entry_points().select(group='acwf.overrides', name=over['entrypoint'])
                override_func = found[over['entrypoint']].load()
                override_func(builder, **over['kwargs'])

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
