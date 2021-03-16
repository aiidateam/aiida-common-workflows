# -*- coding: utf-8 -*-
"""Tests for the :mod:`aiida_common_workflows.workflows.relax.quantum_espresso.generator` module."""
import pytest

from qe_tools import CONSTANTS

from aiida_common_workflows.workflows.relax.quantum_espresso.workchain import QuantumEspressoCommonRelaxWorkChain
from aiida_common_workflows.workflows.relax.generator import ElectronicType, RelaxType, SpinType


@pytest.mark.usefixtures('sssp')
def test_relax_type(generate_code, generate_structure):
    """Test the ``relax_type`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si',))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.NONE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'scf'
    assert 'CELL' not in builder['base']['pw']['parameters'].attributes

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.POSITIONS)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'relax'
    assert 'CELL' not in builder['base']['pw']['parameters'].attributes

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.CELL)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'all'

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.SHAPE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'shape'

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.POSITIONS_CELL)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'all'

    builder = generator.get_builder(structure, engines, relax_type=RelaxType.POSITIONS_SHAPE)
    assert builder['base']['pw']['parameters']['CONTROL']['calculation'] == 'vc-relax'
    assert builder['base']['pw']['parameters']['CELL']['cell_dofree'] == 'shape'

    with pytest.raises(ValueError):
        builder = generator.get_builder(structure, engines, relax_type=RelaxType.VOLUME)

    with pytest.raises(ValueError):
        builder = generator.get_builder(structure, engines, relax_type=RelaxType.POSITIONS_VOLUME)


@pytest.mark.usefixtures('sssp')
def test_spin_type(generate_code, generate_structure):
    """Test the ``spin_type`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si',))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure, engines, spin_type=SpinType.NONE)
    assert 'nspin' not in builder['base']['pw']['parameters']['SYSTEM']

    builder = generator.get_builder(structure, engines, spin_type=SpinType.COLLINEAR)
    assert builder['base']['pw']['parameters']['SYSTEM']['nspin'] == 2
    assert builder['base']['pw']['parameters']['SYSTEM']['starting_magnetization'] is not None


@pytest.mark.usefixtures('sssp')
def test_electronic_type(generate_code, generate_structure):
    """Test the ``electronic_type`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si',))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    builder = generator.get_builder(structure, engines, electronic_type=ElectronicType.METAL)
    assert builder['base']['pw']['parameters']['SYSTEM']['degauss'] is not None
    assert builder['base']['pw']['parameters']['SYSTEM']['smearing'] is not None

    builder = generator.get_builder(structure, engines, electronic_type=ElectronicType.INSULATOR)
    assert builder['base']['pw']['parameters']['SYSTEM']['occupations'] == 'fixed'
    assert 'degauss' not in builder['base']['pw']['parameters']['SYSTEM']
    assert 'smearing' not in builder['base']['pw']['parameters']['SYSTEM']


@pytest.mark.usefixtures('sssp')
def test_threshold_forces(generate_code, generate_structure):
    """Test the ``threshold_forces`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si',))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    threshold_forces = 0.1
    expected = threshold_forces * CONSTANTS.bohr_to_ang / CONSTANTS.ry_to_ev
    builder = generator.get_builder(structure, engines, threshold_forces=threshold_forces)
    assert builder['base']['pw']['parameters']['CONTROL']['forc_conv_thr'] == expected


@pytest.mark.usefixtures('sssp')
def test_threshold_stress(generate_code, generate_structure):
    """Test the ``threshold_stress`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si',))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    threshold_stress = 0.1
    expected = threshold_stress * CONSTANTS.bohr_to_ang**3 / CONSTANTS.ry_to_ev
    builder = generator.get_builder(structure, engines, threshold_stress=threshold_stress)
    assert builder['base']['pw']['parameters']['CELL']['press_conv_thr'] == expected


@pytest.mark.usefixtures('sssp')
def test_magnetization_per_site(generate_code, generate_structure):
    """Test the ``magnetization_per_site`` keyword argument."""
    code = generate_code('quantum_espresso.pw')
    structure = generate_structure(symbols=('Si', 'Ge'))
    generator = QuantumEspressoCommonRelaxWorkChain.get_input_generator()
    engines = {'relax': {'code': code, 'options': {}}}

    magnetization_per_site = [0.0, 0.1, 0.2]
    with pytest.raises(ValueError):
        builder = generator.get_builder(structure, engines, magnetization_per_site=magnetization_per_site)

    magnetization_per_site = [0.0, 0.1]
    builder = generator.get_builder(
        structure, engines, magnetization_per_site=magnetization_per_site, spin_type=SpinType.COLLINEAR
    )
    assert builder['base']['pw']['parameters']['SYSTEM']['starting_magnetization'] == {'Si': 0.0, 'Ge': 0.025}
