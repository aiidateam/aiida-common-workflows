"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso` module."""
import pytest
from aiida import engine, plugins
from aiida_common_workflows.workflows.relax.generator import ElectronicType, RelaxType, SpinType


@pytest.fixture
def generator():
    return plugins.WorkflowFactory('common_workflows.relax.quantum_espresso').get_input_generator()


@pytest.fixture
def default_builder_inputs(generate_code, generate_structure):
    """Return a dictionary with minimum required inputs for the ``get_builder`` method of the inputs generator."""
    return {
        'structure': generate_structure(symbols=('Si',)),
        'engines': {
            'relax': {
                'code': generate_code('quantumespresso.pw').store().uuid,
                'options': {'resources': {'num_machines': 1, 'tot_num_mpiprocs': 1}},
            }
        },
    }


@pytest.mark.usefixtures('sssp')
def test_get_builder(generator, default_builder_inputs):
    """Test the ``get_builder`` with default arguments."""
    builder = generator.get_builder(**default_builder_inputs)
    assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.usefixtures('sssp')
@pytest.mark.skip('Running this test will fail with an `UnroutableError` in `kiwipy`.')
def test_submit(generator, default_builder_inputs):
    """Test submitting the builder returned by ``get_builder`` called with default arguments.

    This will actually create the ``WorkChain`` instance, so if it doesn't raise, that means the input spec was valid.
    """
    builder = generator.get_builder(**default_builder_inputs)
    engine.submit(builder)


@pytest.mark.usefixtures('sssp')
def test_options(generator, default_builder_inputs):
    """Test that the ``options`` of the ``engines`` argument are added to all namespaces."""
    inputs = default_builder_inputs
    builder = generator.get_builder(**inputs)
    assert isinstance(builder, engine.ProcessBuilder)
    assert builder.base.pw.metadata.options.resources == inputs['engines']['relax']['options']['resources']
    assert builder.base_final_scf.pw.metadata.options.resources == inputs['engines']['relax']['options']['resources']


@pytest.mark.usefixtures('sssp')
def test_supported_electronic_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``electronic_types``."""
    inputs = default_builder_inputs

    for electronic_type in generator.spec().inputs['electronic_type'].choices:
        inputs['electronic_type'] = electronic_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.usefixtures('sssp')
def test_supported_relax_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``relax_types``."""
    inputs = default_builder_inputs

    for relax_type in generator.spec().inputs['relax_type'].choices:
        inputs['relax_type'] = relax_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.usefixtures('sssp')
def test_supported_spin_types(generator, default_builder_inputs):
    """Test calling ``get_builder`` for the supported ``spin_types``."""
    inputs = default_builder_inputs

    for spin_type in generator.spec().inputs['spin_type'].choices:
        inputs['spin_type'] = spin_type
        builder = generator.get_builder(**inputs)
        assert isinstance(builder, engine.ProcessBuilder)


@pytest.mark.usefixtures('sssp')
def test_relax_type(generator, generate_code, generate_structure):
    """Test the ``relax_type`` keyword argument."""
    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si',))
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.NONE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'scf'
    assert 'CELL' not in builder['base']['pw']['parameters'].base.attributes.all

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.POSITIONS)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'relax'
    assert 'CELL' not in builder['base']['pw']['parameters'].base.attributes.all

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.CELL)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'all'

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.SHAPE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'shape'

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.POSITIONS_CELL)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'all'

    builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.POSITIONS_SHAPE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'shape'

    with pytest.raises(ValueError):
        builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.VOLUME)

    with pytest.raises(ValueError):
        builder = generator.get_builder(structure=structure, engines=engines, relax_type=RelaxType.POSITIONS_VOLUME)


@pytest.mark.usefixtures('sssp')
def test_spin_type(generator, generate_code, generate_structure):
    """Test the ``spin_type`` keyword argument."""
    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si',))
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure=structure, engines=engines, spin_type=SpinType.NONE)
    assert 'nspin' not in builder['base']['pw']['parameters']['SYSTEM']

    builder = generator.get_builder(structure=structure, engines=engines, spin_type=SpinType.COLLINEAR)
    assert builder['base']['pw']['parameters']['SYSTEM']['nspin'] == 2
    assert builder['base']['pw']['parameters']['SYSTEM']['starting_magnetization'] is not None


@pytest.mark.usefixtures('sssp')
def test_electronic_type(generator, generate_code, generate_structure):
    """Test the ``electronic_type`` keyword argument."""
    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si',))
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure=structure, engines=engines, electronic_type=ElectronicType.METAL)
    assert builder['base']['pw']['parameters']['SYSTEM']['degauss'] is not None
    assert builder['base']['pw']['parameters']['SYSTEM']['smearing'] is not None

    builder = generator.get_builder(structure=structure, engines=engines, electronic_type=ElectronicType.INSULATOR)
    assert builder['base']['pw']['parameters']['SYSTEM']['occupations'] == 'fixed'
    assert 'degauss' not in builder['base']['pw']['parameters']['SYSTEM']
    assert 'smearing' not in builder['base']['pw']['parameters']['SYSTEM']


@pytest.mark.usefixtures('sssp')
def test_threshold_forces(generator, generate_code, generate_structure):
    """Test the ``threshold_forces`` keyword argument."""
    from qe_tools import CONSTANTS

    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si',))
    engines = {'relax': {'code': code, 'options': {}}}

    threshold_forces = 0.1
    expected = threshold_forces * CONSTANTS.bohr_to_ang / CONSTANTS.ry_to_ev
    builder = generator.get_builder(structure=structure, engines=engines, threshold_forces=threshold_forces)
    assert builder['base']['pw']['parameters']['CONTROL']['forc_conv_thr'] == expected


@pytest.mark.usefixtures('sssp')
def test_threshold_stress(generator, generate_code, generate_structure):
    """Test the ``threshold_stress`` keyword argument."""
    from qe_tools import CONSTANTS

    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si',))
    engines = {'relax': {'code': code, 'options': {}}}

    threshold_stress = 0.1
    expected = threshold_stress * CONSTANTS.bohr_to_ang**3 / CONSTANTS.ry_to_ev
    builder = generator.get_builder(structure=structure, engines=engines, threshold_stress=threshold_stress)
    assert builder['base']['pw']['parameters']['CELL']['press_conv_thr'] == expected


@pytest.mark.usefixtures('sssp')
def test_magnetization_per_site(generator, generate_code, generate_structure):
    """Test the ``magnetization_per_site`` keyword argument."""
    code = generate_code('quantumespresso.pw')
    structure = generate_structure(symbols=('Si', 'Ge'))
    engines = {'relax': {'code': code, 'options': {}}}

    magnetization_per_site = [0.0, 0.1, 0.2]
    with pytest.raises(ValueError):
        builder = generator.get_builder(
            structure=structure, engines=engines, magnetization_per_site=magnetization_per_site
        )

    magnetization_per_site = [0.0, 0.1]
    builder = generator.get_builder(
        structure=structure,
        engines=engines,
        magnetization_per_site=magnetization_per_site,
        spin_type=SpinType.COLLINEAR,
    )
    assert builder['base']['pw']['parameters']['SYSTEM']['starting_magnetization'] == {'Si': 0.0, 'Ge': 0.025}
