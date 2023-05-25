# -*- coding: utf-8 -*-
"""Equation of state workflow that can use any code plugin implementing the common relax workflow."""
import inspect

from aiida import orm
from aiida.common import AttributeDict, exceptions
from aiida.engine import WorkChain, if_
from aiida.plugins import CalculationFactory, DataFactory, WorkflowFactory

from aiida_common_workflows.common.properties import PhononProperty
from aiida_common_workflows.workflows.relax.generator import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain

PhonopyCalculation = CalculationFactory('phonopy.phonopy')
PreProcessData = DataFactory('phonopy.preprocess')
PhonopyData = DataFactory('phonopy.phonopy')


def validate_inputs(value, _):
    """Validate the entire input namespace."""
    # Validate that the provided ``generator_inputs`` are valid for the associated input generator.
    process_class = WorkflowFactory(value['sub_process_class'])
    generator = process_class.get_input_generator()

    try:
        generator.get_builder(structure=value['structure'], **value['generator_inputs'])
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


def validate_matrix(inputs, _):
    """Validate the `supercell_matrix` and `primitive_matrix` inputs."""
    value = inputs.get_list()

    if not len(value) == 3:
        return 'need exactly 3 diagonal elements or 3x3 arrays.'

    for row in value:
        if isinstance(row, list):
            if not len(row) in [0, 3]:
                return 'matrix need to have 3x1 or 3x3 shape.'
            for element in row:
                if not isinstance(element, (int, float)):
                    return (
                        f'type `{type(element)}` of {element} is not an accepted '
                        'type in matrix; only `int` and `float` are valid.'
                    )


def validate_phonon_property(value, _):
    """Validate the `generator_inputs.phonon_property` input."""
    if value is not None and isinstance(value, str):
        value = PhononProperty(value)


class FrozenPhononsWorkChain(WorkChain):
    """Workflow to compute the harmonic phonons for a given crystal structure using finite displacements.

    .. note:: the non-analitical costants, i.e. Born effective charges and
        dielectric tensors are not applied nor calculated here (only relevant for insulators).
    """

    _ENABLED_DISPLACEMENT_GENERATOR_FLAGS = {
        'distance': [float],
        'is_plusminus': ['auto', float],
        'is_diagonal': [bool],
        'is_trigonal': [bool],
        'number_of_snapshots': [int, None],
        'random_seed': [int, None],
        'cutoff_frequency': [float, None],
    }

    _RUN_PREFIX = 'scf_supercell'

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.input('structure', valid_type=orm.StructureData, help='The structure at equilibrium volume.')
        spec.input(
            'supercell_matrix', valid_type=orm.List, required=False, validator=validate_matrix,
            help='Supercell matrix that defines the supercell from the unitcell.',
        )
        spec.input(
            'primitive_matrix', valid_type=orm.List, required=False, validator=validate_matrix,
            help='Primitive matrix that defines the primitive cell from the unitcell.',
        )
        spec.input_namespace(
            'symmetry',
            help='Namespace for symmetry related inputs.',
        )
        spec.input(
            'symmetry.symprec', valid_type=orm.Float, default=lambda:orm.Float(1e-5),
            help='Symmetry tolerance for space group analysis on the input structure.',
        )
        spec.input(
            'symmetry.distinguish_kinds', valid_type=orm.Bool, default=lambda:orm.Bool(False),
            help='Whether or not to distinguish atom with same species but different names with symmetries.',
        )
        spec.input(
            'symmetry.is_symmetry', valid_type=orm.Bool, default=lambda:orm.Bool(True),
            help='Whether using or not the space group symmetries.',
        )
        spec.input(
            'displacement_generator', valid_type=orm.Dict, required=False,
            help=(
                'Info for displacements generation. The following flags are allowed:\n ' +
                '\n '.join(f'{flag_name}' for flag_name in cls._ENABLED_DISPLACEMENT_GENERATOR_FLAGS)
            ),
            validator=cls._validate_displacements,
        )
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
        # spec.input('generator_inputs.phonon_property', valid_type=(PhononProperty, str), required=False, non_db=True,
        #     help='List containing the initial magnetization per atomic site.', validator=validate_phonon_property)
        spec.expose_inputs(
            PhonopyCalculation, namespace='phonopy',
            namespace_options={
                'required': False, 'populate_defaults': False,
                'help': (
                    'Inputs for the `PhonopyCalculation` that will'
                    'be used to calculate the inter-atomic force constants, or for post-processing.'
                )
            },
            exclude=['phonopy_data', 'force_constants'],
        )

        spec.input_namespace('sub_process', dynamic=True, populate_defaults=False)
        spec.input('sub_process_class', non_db=True, validator=validate_sub_process_class)
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.run_init,
            cls.inspect_init,
            cls.run_supercells,
            cls.inspect_supercells,
            cls.set_phonopy_data,
            if_(cls.should_run_phonopy)(
                cls.run_phonopy,
                cls.inspect_phonopy,
            )
        )
        spec.output_namespace('structures', valid_type=orm.StructureData,
            help='The relaxed structures at each scaling factor.')
        spec.output_namespace('forces', valid_type=orm.ArrayData,
            help='The computed forces of the structures at displacement.')
        # spec.output_namespace('total_energies', valid_type=orm.Float,
        #     help='The computed total energy of the relaxed structures at each scaling factor.')
        # spec.output_namespace('total_magnetizations', valid_type=orm.Float,
        #     help='The computed total magnetization of the relaxed structures at each scaling factor.')
        spec.output(
            'phonopy_data', valid_type=PhonopyData, required=True,
            help=(
                'The phonopy data with supercells displacements, forces'
                ' to use in the post-processing calculation.'
            ),
        )
        spec.expose_outputs(PhonopyCalculation, namespace='output_phonopy', namespace_options={'required': False})

        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='At least one of the `{cls}` sub processes did not finish successfully.')
        spec.exit_code(401, 'ERROR_PHONOPY_CALCULATION_FAILED',
            message='The phonopy calculation did not finish correctly.')

    @classmethod
    def _validate_displacements(cls, value, _):
        """Validate the ``displacements`` input namespace."""
        if value:
            value_dict = value.get_dict()
            enabled_dict = cls._ENABLED_DISPLACEMENT_GENERATOR_FLAGS
            unknown_flags = set(value_dict.keys()) - set(enabled_dict.keys())
            if unknown_flags:
                return (
                    f"Unknown flags in 'displacements': {unknown_flags}."
                    # f"allowed flags are {cls._ENABLED_DISPLACEMENT_GENERATOR_FLAGS.keys()}."
                )
            invalid_values = [
                value_dict[key]
                for key in value_dict.keys()
                if not (type(value_dict[key]) in enabled_dict[key] or value_dict[key] in enabled_dict[key])
            ]
            if invalid_values:
                return f'Displacement options must be of the correct type; got invalid values {invalid_values}.'

    def get_sub_workchain_builder(self, supercell, reference_workchain=None):
        """Return the builder for the relax workchain."""
        process_class = WorkflowFactory(self.inputs.sub_process_class)

        base_inputs = {'structure': supercell}
        if reference_workchain is not None:
            base_inputs['reference_workchain'] = reference_workchain

        builder = process_class.get_input_generator().get_builder(
            relax_type=RelaxType.NONE,
            **base_inputs,
            **self.inputs.generator_inputs
        )
        builder._update(**self.inputs.get('sub_process', {}))  # pylint: disable=protected-access

        return builder, supercell

    def run_init(self):
        """Run the first workchain."""
        preprocess_inputs = {'structure': self.inputs.structure}

        for input_ in ['supercell_matrix', 'primitive_matrix', 'displacement_generator',]:
            if input_ in self.inputs:
                preprocess_inputs.update({input_: self.inputs[input_]})
        for input_ in ['symprec', 'is_symmetry', 'distinguish_kinds']:
            if input_ in self.inputs['symmetry']:
                preprocess_inputs.update({input_: self.inputs['symmetry'][input_]})

        preprocess_data = PreProcessData.generate_preprocess_data(**preprocess_inputs)
        self.ctx.preprocess_data = preprocess_data

        supercell = preprocess_data.calcfunctions.get_supercell()

        builder, supercell = self.get_sub_workchain_builder(supercell)
        self.report(f'submitting `{builder.process_class.__name__}` for pristine supercell')
        self.ctx.reference_workchain = self.submit(builder)
        self.ctx.structures = [supercell]
        self.to_context(**{f'{self._RUN_PREFIX}_0':self.ctx.reference_workchain})

    def inspect_init(self):
        """Check that the first workchain finished successfully or abort the workchain."""
        if not self.ctx[f'{self._RUN_PREFIX}_0'].is_finished_ok:
            self.report('Initial sub process did not finish successful so aborting the workchain.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)  # pylint: disable=no-member

    def run_supercells(self):
        """Run the sub process at each supercell structureto compute the structure volume and total energy."""
        supercells = self.ctx.preprocess_data.calcfunctions.get_supercells_with_displacements()

        for key, supercell in supercells.items():
            num = key.split('_')[-1]
            label = f'{self._RUN_PREFIX}_{num}'

            reference_workchain = self.ctx.reference_workchain
            builder, structure = self.get_sub_workchain_builder(
                supercell, reference_workchain=reference_workchain
            )
            self.report(f'submitting `{builder.process_class.__name__}` for displacement {num}')
            self.ctx.structures.append(structure)
            self.to_context(**{label: self.submit(builder)})

    def inspect_supercells(self):
        """Inspect all children workflows to make sure they finished successfully."""
        failed_runs = []

        for label, workchain in self.ctx.items():
            if label.startswith(self._RUN_PREFIX):
                if workchain.is_finished_ok:
                    index = int(label.split('_')[-1])
                    forces = workchain.outputs.forces
                    self.out(f'forces.forces_{index}', forces)
                    self.out(f'structures.{index}', self.ctx.structures[index])
                else:
                    failed_runs.append(workchain.pk)

        if failed_runs:
            self.report('one or more workchains did not finish succesfully')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=self.inputs.sub_process_class)  # pylint: disable=no-member

    def set_phonopy_data(self):
        """Set the `PhonopyData` in context for Phonopy post-processing calculation."""
        self.ctx.phonopy_data = self.ctx.preprocess_data.calcfunctions.generate_phonopy_data(**self.outputs['forces'])
        self.out('phonopy_data', self.ctx.phonopy_data)

    def should_run_phonopy(self):
        """Return whether to run a PhonopyCalculation."""
        return 'phonopy' in self.inputs

    def run_phonopy(self):
        """Run a `PhonopyCalculation` to get the force constants."""
        inputs = AttributeDict(self.exposed_inputs(PhonopyCalculation, namespace='phonopy'))
        inputs.phonopy_data = self.ctx.phonopy_data

        key = 'phonopy_calculation'
        inputs.metadata.call_link_label = key

        future = self.submit(PhonopyCalculation, **inputs)
        self.report(f'submitting `PhonopyCalculation` <PK={future.pk}>')
        self.to_context(**{key: future})

    def inspect_phonopy(self):
        """Inspect that the `PhonopyCalculation` finished successfully."""
        calc = self.ctx.phonopy_calculation

        if calc.is_failed:
            self.report(f'`PhonopyCalculation` failed with exit status {calc.exit_status}')
            return self.exit_codes.ERROR_PHONOPY_CALCULATION_FAILED

        self.out_many(self.exposed_outputs(calc, PhonopyCalculation, namespace='output_phonopy'))
