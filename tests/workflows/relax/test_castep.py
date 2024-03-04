"""Tests for the :mod:`aiida_common_workflows.workflows.relax.castep` module."""
import copy

import pytest
from aiida import engine, plugins
from aiida.orm import StructureData
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ase.build.bulk import bulk


@pytest.fixture
def generator():
    return plugins.WorkflowFactory('common_workflows.relax.castep').get_input_generator()


@pytest.fixture
def nacl(with_database):
    """Get an NaCl structure"""
    structure = StructureData(ase=bulk('NaCl', 'rocksalt', 4.2))
    return structure


@pytest.fixture
def si(with_database):
    """Get an NaCl structure"""
    structure = StructureData(ase=bulk('Si', 'diamond', 5.43))
    return structure


@pytest.fixture
def castep_code(generate_code):
    """Get a Code object"""
    code = generate_code('castep.castep')
    code.label = 'castep'
    return code


@pytest.fixture
def with_otfg(with_database):
    """Ensure has OTFG"""
    from aiida_common_workflows.workflows.relax.castep.generator import ensure_otfg_family

    ensure_otfg_family('C19')


@pytest.fixture
def default_builder_inputs(generate_code, generate_structure, castep_code):
    """Return a dictionary with minimum required inputs for the ``get_builder`` method of the inputs generator."""
    return {
        'structure': generate_structure(symbols=('Si',)),
        'engines': {
            'relax': {'code': castep_code, 'options': {'resources': {'num_machines': 1, 'tot_num_mpiprocs': 1}}}
        },
    }


def test_get_builder(generator, default_builder_inputs):
    """Test the ``get_builder`` with default arguments."""
    builder = generator.get_builder(**default_builder_inputs)
    assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.skip('Running this test will fail with an `UnroutableError` in `kiwipy`.')
def test_submit(generator, default_builder_inputs):
    """Test submitting the builder returned by ``get_builder`` called with default arguments.

    This will actually create the ``WorkChain`` instance, so if it doesn't raise, that means the input spec was valid.
    """
    builder = generator.get_builder(**default_builder_inputs)
    engine.submit(builder)


def test_supported_electronic_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``electronic_types``."""
    inputs = default_builder_inputs

    for electronic_type in generator.spec().inputs['electronic_type'].choices:
        inputs['electronic_type'] = electronic_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


def test_supported_relax_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``relax_types``."""
    inputs = default_builder_inputs

    for relax_type in generator.spec().inputs['relax_type'].choices:
        inputs['relax_type'] = relax_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


def test_supported_spin_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``spin_types``."""
    inputs = default_builder_inputs

    for spin_type in generator.spec().inputs['spin_type'].choices:
        inputs['spin_type'] = spin_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


def test_calc_generator(nacl, castep_code, with_otfg):
    """Test the functionality of the calculation generator"""
    from aiida_castep.data.otfg import OTFGGroup
    from aiida_common_workflows.workflows.relax.castep.generator import generate_inputs_calculation

    protcol = {
        'kpoints_spacing': 0.05,
        'calc': {'parameters': {'task': 'geometryoptimisation', 'basis_precision': 'medium'}},
    }
    override = {'calc': {'parameters': {'cut_off_energy': 220}}}
    otfg = OTFGGroup.collection.get(label='C19')
    generated = generate_inputs_calculation(protcol, castep_code, nacl, otfg, override)

    assert 'structure' in generated
    paramd = generated['parameters'].get_dict()
    assert 'basis_precision' not in paramd
    assert 'kpoints' in generated


def test_base_generator(castep_code, nacl, with_otfg):
    """Test for generating the Base namespace"""
    from aiida_castep.data.otfg import OTFGGroup
    from aiida_common_workflows.workflows.relax.castep.generator import generate_inputs_base

    protcol = {
        'kpoints_spacing': 0.05,
        'max_iterations': 5,
        'calc': {'parameters': {'task': 'geometryoptimisation', 'basis_precision': 'medium'}},
    }
    override = {'calc': {'parameters': {'cut_off_energy': 220}, 'metadata': {'label': 'test'}}}
    otfg = OTFGGroup.collection.get(label='C19')
    generated = generate_inputs_base(protcol, castep_code, nacl, otfg, override)

    assert 'structure' in generated['calc']
    paramd = generated['calc']['parameters'].get_dict()
    assert 'basis_precision' not in paramd
    assert 'kpoints_spacing' in generated
    assert 'kpoints' not in generated['calc']
    assert generated['calc']['metadata']['label'] == 'test'


def test_relax_generator(generator, castep_code, nacl, with_otfg):
    """Test for generating the relax namespace"""
    from aiida_castep.data.otfg import OTFGGroup
    from aiida_common_workflows.workflows.relax.castep.generator import generate_inputs_relax

    protocol = generator.get_protocol('moderate')['relax']
    override = {
        'base': {
            'metadata': {'label': 'test'},
            'calc': {'parameters': {'cut_off_energy': 220}, 'metadata': {'label': 'test'}},
        }
    }
    otfg = OTFGGroup.collection.get(label='C19')
    generated = generate_inputs_relax(protocol, castep_code, nacl, otfg, override)

    assert 'structure' in generated
    paramd = generated['calc']['parameters']
    assert 'basis_precision' not in paramd
    assert 'kpoints_spacing' in generated['base']
    assert 'kpoints' not in generated['calc']

    assert generated['calc']['metadata']['label'] == 'test'
    assert generated['base']['metadata']['label'] == 'test'


def test_generate_inputs(generator, castep_code, nacl, si):
    """
    Test for the generator
    """
    from aiida_common_workflows.workflows.relax.castep.generator import generate_inputs

    protocol = generator.get_protocol('moderate')
    override = {'base': {'metadata': {'label': 'test'}, 'calc': {}}}

    output = generate_inputs(WorkflowFactory('castep.relax'), copy.deepcopy(protocol), castep_code, si, override)
    assert output['calc']['parameters']['basis_precision'] == 'fine'
    assert 'structure' not in output['calc']

    output = generate_inputs(WorkflowFactory('castep.base'), copy.deepcopy(protocol), castep_code, si, override)
    assert output['calc']['parameters']['PARAM']['basis_precision'] == 'fine'
    assert 'structure' in output['calc']


def test_input_generator(generator, castep_code, nacl, si):
    """Test for the input generator"""
    engines = {'relax': {'code': castep_code, 'options': {}}}
    builder = generator.get_builder(structure=si, engines=engines, protocol='moderate')
    param = builder.calc.parameters.get_dict()
    assert param['cut_off_energy'] == 326
    assert builder.base.kpoints_spacing == pytest.approx(0.023873, abs=1e-6)

    builder = generator.get_builder(structure=si, engines=engines, protocol='moderate', relax_type=RelaxType.POSITIONS)
    assert 'fix_all_cell' in builder.calc.parameters.get_dict()

    builder = generator.get_builder(
        structure=si, engines=engines, protocol='moderate', relax_type=RelaxType.POSITIONS_SHAPE
    )
    assert 'fix_vol' in builder.calc.parameters.get_dict()

    builder = generator.get_builder(structure=si, engines=engines, protocol='moderate', spin_type=SpinType.COLLINEAR)
    assert 'SPINS' in builder.calc.settings.get_dict()

    builder = generator.get_builder(
        structure=si, engines=engines, protocol='moderate', spin_type=SpinType.NON_COLLINEAR
    )
    assert builder.calc.settings['SPINS'][0] == [1.0, 1.0, 1.0]

    builder = generator.get_builder(
        structure=si, engines=engines, protocol='moderate', electronic_type=ElectronicType.INSULATOR
    )
    assert builder.calc.settings is None
    assert builder.base.kpoints_spacing == pytest.approx(0.023873, abs=1e-6)


def test_otfg_upload(with_otfg):
    """
    Test uploading customized OTFG family
    """
    from aiida_castep.data.otfg import OTFGGroup
    from aiida_common_workflows.workflows.relax.castep.generator import ensure_otfg_family

    # Initial upload
    ensure_otfg_family('C19V2')
    assert OTFGGroup.collection.get(label='C19V2')

    # Second call should not error
    ensure_otfg_family('C19V2')
    assert OTFGGroup.collection.get(label='C19V2')

    # Second call with forced update
    ensure_otfg_family('C19V2', force_update=True)

    group = OTFGGroup.collection.get(label='C19V2')
    found = False
    for node in group.nodes:
        if node.element == 'La':
            assert node.entry == 'La 2|2.3|5|6|7|50U:60:51:52:43{4f0.1}(qc=4.5)'
            found = True
    assert found
