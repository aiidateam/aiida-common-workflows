# -*- coding: utf-8 -*-
"""Equation of state workflow that can use any code plugin implementing the common relax workflow."""
import inspect

from aiida import orm
from aiida.common import exceptions
from aiida.engine import WorkChain, append_, calcfunction
from aiida.plugins import WorkflowFactory

from aiida_common_workflows.workflows.relax.generator import RelaxType, SpinType, ElectronicType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain

ForceSetWorkChain = WorkflowFactory('phonopy.force_set')

def validate_common_inputs(value, _):
    """Validate the entire input namespace."""
    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['sub_process_class'])
    generator = process_class.get_input_generator()

    try:
        generator.get_builder(value['structure'], **value['generator_inputs'])
    except Exception as exc:  # pylint: disable=broad-except
        return f'`{generator.__class__.__name__}.get_builder()` fails for the provided `generator_inputs`: {exc}'

def validate_sub_process_class(value, _):
    """Validate the sub process class."""
    try:
        process_class = WorkflowFactory(value)
    except exceptions.EntryPointError:
        return f'`{value}` is not a valid or registered workflow entry point.'

    if not inspect.isclass(process_class) or not issubclass(process_class, CommonRelaxWorkChain):
        return f'`{value}` is not a subclass of the `CommonRelaxWorkChain` common workflow.'


class CommonForceSetStateWorkChain(ForceSetWorkChain):
    """
    Workflow to compute automatically the force set of a given structure
    using the frozen phonons approach.
    
    Phonopy is used to produce structures with displacements,
    while the forces are calculated with a quantum engine of choice.
    """

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input_namespace('generator_inputs',
            help='The inputs that will be passed to the input generator of the specified `sub_process`.')
        spec.input('generator_inputs.engines', valid_type=dict, non_db=True)
        spec.input('generator_inputs.protocol', valid_type=str, non_db=True,
            help='The protocol to use when determining the workchain inputs.')
        spec.input('generator_inputs.spin_type', valid_type=(SpinType, str), required=False, non_db=True,
            help='The type of spin for the calculation.')
        spec.input('generator_inputs.electronic_type', valid_type=(ElectronicType, str), required=False, non_db=True,
            help='The type of electronics (insulator/metal) for the calculation.')
        spec.input('generator_inputs.magnetization_per_site', valid_type=(list, tuple), required=False, non_db=True,
            help='List containing the initial magnetization per atomic site.')
        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_common_inputs

        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED', # can't we say exactly which are not finished ok?
            message='At least one of the `{cls}` sub processes did not finish successfully.')


    def get_sub_workchain_builder(self, structure, reference_workchain=None):
        """Return the builder for the scf workchain."""
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        relax_type = {'relax_type':RelaxType.NONE} # scf type   

        builder = process_class.get_input_generator().get_builder(
            structure,
            # v : useful in the future for using the charge density to make calcs faster?
            reference_workchain=reference_workchain, 
            **self.inputs.generator_inputs,
            **relax_type,
        )
        builder._update(**self.inputs.get('sub_process', {}))  # pylint: disable=protected-access

        return builder

    def run_init(self): # can be usefull for restarting from pristine structure
        """Run the first workchain."""
        scale_factor = self.get_scale_factors()[0]
        builder, structure = self.get_sub_workchain_builder(scale_factor)
        self.report(f'submitting `{builder.process_class.__name__}` for scale_factor `{scale_factor}`')
        self.ctx.reference_workchain = self.submit(builder)
        self.ctx.structures = [structure]
        self.to_context(children=append_(self.ctx.reference_workchain))

    def inspect_init(self):
        """Check that the first workchain finished successfully or abort the workchain."""
        if not self.ctx.children[0].is_finished_ok:
            self.report('Initial sub process did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)  # pylint: disable=no-member

    def run_forces(self):
        """Run supercell force calculations."""
        for key, supercell in self.ctx.supercells.items():
            label = "force_calc_%s" % key.split("_")[-1]
            builder = self.get_sub_workchain_builder(supercell)
            builder.metadata.label = label # very necessary?
            future = self.submit(builder)
            self.report("submitting `{builder.process_class.__name__}` <PK={}> with {} as structure".format(future.pk, label))
            self.to_context(**{label: future})

    def inspect_forces(self):
        """Inspect all children workflows to make sure they finished successfully."""
        if any([not supercell.is_finished_ok for supercell in self.ctx if supercell.label.startswith("force_calc_") ]):
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)  # pylint: disable=no-member
        
        self.ctx.forces = {}

        for force_run in self.ctx:
            label = force_run.label
            if label.startswith("force_calc_"):
                forces = force_run.outputs.forces
                self.ctx.forces.append({label:forces})
                self.out(f'supercells_forces.{label}', forces)
        
    def run_results:
        """Run final results."""
        pass


