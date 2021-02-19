# -*- coding: utf-8 -*-
"""
Tests from the generator
"""
# pylint: disable=abstract-method,arguments-differ,redefined-outer-name,unused-argument
import copy
import pytest
from aiida.orm import StructureData
from aiida.plugins import WorkflowFactory
from ase.build.bulk import bulk
from aiida_castep.data.otfg import OTFGGroup

from aiida_common_workflows.workflows.relax.castep.workchain import CastepRelaxWorkChain
from aiida_common_workflows.workflows.relax.castep.generator import (
    CastepRelaxInputGenerator, generate_inputs, generate_inputs_base, generate_inputs_calculation,
    generate_inputs_relax, ensure_otfg_family, RelaxType, ElectronicType, SpinType
)


@pytest.fixture
def nacl(with_database):  # pylint: disable=invalid-name
    """Get an NaCl structure"""
    structure = StructureData(ase=bulk('NaCl', 'rocksalt', 4.2))
    return structure


@pytest.fixture
def si(with_database):  # pylint: disable=invalid-name
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
    ensure_otfg_family('C19')


def test_calc_generator(nacl, castep_code, with_otfg):
    """Test the functionality of the calculation generator"""
    protcol = {
        'kpoints_spacing': 0.05,
        'calc': {
            'parameters': {
                'task': 'geometryoptimisation',
                'basis_precision': 'medium'
            }
        }
    }
    override = {'calc': {'parameters': {'cut_off_energy': 220}}}
    otfg = OTFGGroup.objects.get(label='C19')
    generated = generate_inputs_calculation(protcol, castep_code, nacl, otfg, override)

    assert 'structure' in generated
    paramd = generated['parameters'].get_dict()
    assert 'basis_precision' not in paramd
    assert 'kpoints' in generated


def test_base_generator(castep_code, nacl, with_otfg):
    """Test for generating the Base namespace"""
    protcol = {
        'kpoints_spacing': 0.05,
        'max_iterations': 5,
        'calc': {
            'parameters': {
                'task': 'geometryoptimisation',
                'basis_precision': 'medium'
            }
        }
    }
    override = {'calc': {'parameters': {'cut_off_energy': 220}, 'metadata': {'label': 'test'}}}
    otfg = OTFGGroup.objects.get(label='C19')
    generated = generate_inputs_base(protcol, castep_code, nacl, otfg, override)

    assert 'structure' in generated['calc']
    paramd = generated['calc']['parameters'].get_dict()
    assert 'basis_precision' not in paramd
    assert 'kpoints_spacing' in generated
    assert 'kpoints' not in generated['calc']
    assert generated['calc']['metadata']['label'] == 'test'


def test_relax_generator(castep_code, nacl, with_otfg):
    """Test for generating the relax namespace"""
    CastepRelaxWorkChain = WorkflowFactory('castep.relax')  # pylint: disable=invalid-name
    protocol = CastepRelaxInputGenerator(process_class=CastepRelaxWorkChain).get_protocol('moderate')['relax']
    override = {
        'base': {
            'metadata': {
                'label': 'test'
            },
            'calc': {
                'parameters': {
                    'cut_off_energy': 220
                },
                'metadata': {
                    'label': 'test'
                }
            }
        }
    }
    otfg = OTFGGroup.objects.get(label='C19')
    generated = generate_inputs_relax(protocol, castep_code, nacl, otfg, override)

    assert 'structure' in generated
    paramd = generated['calc']['parameters']
    assert 'basis_precision' not in paramd
    assert 'kpoints_spacing' in generated['base']
    assert 'kpoints' not in generated['calc']

    assert generated['calc']['metadata']['label'] == 'test'
    assert generated['base']['metadata']['label'] == 'test'


def test_generate_inputs(castep_code, nacl, si):  # pylint: disable=invalid-name
    """
    Test for the generator
    """
    protocol = CastepRelaxInputGenerator(process_class=CastepRelaxWorkChain).get_protocol('moderate')
    override = {'base': {'metadata': {'label': 'test'}, 'calc': {}}}

    output = generate_inputs(WorkflowFactory('castep.relax'), copy.deepcopy(protocol), castep_code, si, override)
    assert output['calc']['parameters']['basis_precision'] == 'fine'
    assert 'structure' not in output['calc']

    output = generate_inputs(WorkflowFactory('castep.base'), copy.deepcopy(protocol), castep_code, si, override)
    assert output['calc']['parameters']['PARAM']['basis_precision'] == 'fine'
    assert 'structure' in output['calc']


def test_input_generator(castep_code, nacl, si):  # pylint: disable=invalid-name
    """Test for the input generator"""
    gen = CastepRelaxInputGenerator(process_class=CastepRelaxWorkChain)
    calc_engines = {'relax': {'code': castep_code, 'options': {}}}
    builder = gen.get_builder(si, calc_engines, protocol='moderate')
    param = builder.calc.parameters.get_dict()
    assert param['cut_off_energy'] == 326
    assert builder.base.kpoints_spacing == pytest.approx(0.023873, abs=1e-6)

    builder = gen.get_builder(si, calc_engines, protocol='moderate', relax_type=RelaxType.ATOMS)
    assert 'fix_all_cell' in builder.calc.parameters.get_dict()

    builder = gen.get_builder(si, calc_engines, protocol='moderate', relax_type=RelaxType.ATOMS_SHAPE)
    assert 'fix_vol' in builder.calc.parameters.get_dict()

    builder = gen.get_builder(si, calc_engines, protocol='moderate', spin_type=SpinType.COLLINEAR)
    assert 'SPINS' in builder.calc.settings.get_dict()

    builder = gen.get_builder(si, calc_engines, protocol='moderate', spin_type=SpinType.NON_COLLINEAR)
    assert builder.calc.settings['SPINS'][0] == [1.0, 1.0, 1.0]

    builder = gen.get_builder(si, calc_engines, protocol='moderate', electronic_type=ElectronicType.INSULATOR)
    assert builder.calc.settings is None
    assert builder.base.kpoints_spacing == pytest.approx(0.023873, abs=1e-6)
