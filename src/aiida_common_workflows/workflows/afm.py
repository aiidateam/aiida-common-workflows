from __future__ import annotations

import typing as t
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

from aiida import orm
from aiida.engine import Process
from aiida_workgraph import dynamic, namespace, shelljob, task
from aiida_workgraph.utils import get_dict_from_builder
from ase import Atoms

from aiida_common_workflows.plugins import WorkflowFactory
from aiida_common_workflows.workflows.pp.workchain import CommonPostProcessWorkChain
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain

CommonRelaxWorkChain._process_class = Process
CommonPostProcessWorkChain._process_class = Process


class AfmCase(Enum):
    EMPIRICAL = 'empirical'
    HARTREE = 'hartree'
    HARTREE_RHO = 'hartree_rho'


@task
def write_afm_params(params: dict) -> orm.SinglefileData:
    with TemporaryDirectory() as tmpdir:
        afm_filepath = Path(tmpdir) / 'params.ini'
        with open(afm_filepath, 'w') as config_file:
            for key, value in params.items():
                if isinstance(value, (list, tuple)):
                    value = ' '.join(map(str, value))
                config_file.write(f'{key} {value}\n')
        return orm.SinglefileData(file=afm_filepath.as_posix())


@task
def write_structure_file(structure: Atoms, filename: str) -> orm.SinglefileData:
    with TemporaryDirectory() as tmpdir:
        geom_filepath = Path(tmpdir) / filename
        structure.write(geom_filepath, format='xyz')
        return orm.SinglefileData(file=geom_filepath.as_posix())


@task.graph
def DftJob(
    engine: str,
    structure: orm.StructureData,
    parameters: t.Annotated[
        dict,
        namespace(
            engines=namespace(
                relax=namespace(
                    code=orm.Code,
                    options=dict,
                ),
            ),
            protocol=str,
            relax_type=str,
        ),
    ],
) -> t.Annotated[
    dict,
    task(CommonRelaxWorkChain).outputs,
]:
    workflow = WorkflowFactory(f'common_workflows.relax.{engine.value}')
    input_generator = workflow.get_input_generator()
    parameters['protocol'] = parameters['protocol'].value
    parameters['relax_type'] = parameters['relax_type'].value
    parameters['engines']['relax']['options'] = parameters['engines']['relax']['options'].value
    builder = input_generator.get_builder(structure=structure, **parameters)
    return task(builder._process_class)(**get_dict_from_builder(builder))


@task.graph
def PpJob(
    engine: str,
    parent_folder: orm.RemoteData,
    parameters: t.Annotated[
        dict,
        namespace(
            engines=namespace(
                pp=namespace(
                    code=orm.Code,
                    options=dict,
                ),
            ),
            quantity=str,
        ),
    ],
) -> t.Annotated[
    dict,
    task(CommonPostProcessWorkChain).outputs,
]:
    workflow = WorkflowFactory(f'common_workflows.pp.{engine.value}')
    input_generator = workflow.get_input_generator()
    parameters['quantity'] = parameters['quantity'].value
    parameters['engines']['pp']['options'] = parameters['engines']['pp']['options'].value
    builder = input_generator.get_builder(parent_folder=parent_folder, **parameters)
    return task(builder._process_class)(**get_dict_from_builder(builder))


@task.graph
def AfmWorkflow(
    engine: str,
    case: AfmCase,
    structure: orm.StructureData,
    afm_params: dict,
    relax: bool = False,
    dft_params: t.Annotated[
        dict[str, dict] | None,
        namespace(
            geom=t.Annotated[
                dict,
                DftJob.inputs.parameters,
            ],
            tip=t.Annotated[
                dict,
                DftJob.inputs.parameters,
            ],
        ),
    ] = None,
    pp_params: t.Annotated[
        dict[str, dict] | None,
        namespace(
            hartree_potential=t.Annotated[
                dict,
                PpJob.inputs.parameters,
            ],
            charge_density=t.Annotated[
                dict,
                PpJob.inputs.parameters,
            ],
        ),
    ] = None,
    tip: orm.StructureData = None,
) -> t.Annotated[dict, dynamic(t.Any)]:
    """AFM simulation workflow."""
    if relax:
        assert dft_params, 'Missing DFT parameters'
        geom_dft_params = dft_params.get('geom', {})
        dft_job = DftJob(
            engine=engine,
            structure=structure,
            parameters=geom_dft_params,
        )
        structure = dft_job.relaxed_structure
    else:
        assert structure, 'Missing structure'

    geometry_file = write_structure_file(structure, 'geo.xyz').result

    assert afm_params, 'Missing AFM parameters'
    afm_params_file = write_afm_params(params=afm_params).result

    ljff = shelljob(
        command='ppafm-generate-ljff',
        nodes={
            'geometry': geometry_file,
            'parameters': afm_params_file,
        },
        arguments=[
            '-i',
            'geo.xyz',
            '-f',
            'npy',
        ],
        outputs=['FFLJ.npz'],
    )

    scan_nodes = {
        'parameters': afm_params_file,
        'ljff_data': ljff.FFLJ_npz,
    }

    metadata = {
        'options': {
            'use_symlinks': True,
        }
    }

    if case != AfmCase.EMPIRICAL.name:
        if not relax:
            assert dft_params, 'Missing DFT parameters'
            geom_dft_params = dft_params.get('geom', {})
            geom_dft_params['relax_type'] = orm.Str('none')
            dft_job = DftJob(
                engine=engine,
                structure=structure,
                parameters=geom_dft_params,
            )

        assert pp_params, 'Missing post-processing parameters'
        hartree_params = pp_params.get('hartree_potential', {})
        assert hartree_params, 'Missing Hartree potential post-processing parameters'
        hartree_task = PpJob(
            engine=engine,
            parent_folder=dft_job.remote_folder,
            parameters=hartree_params,
        )

        if case == AfmCase.HARTREE.name:
            elff = shelljob(
                command='ppafm-generate-elff',
                metadata=metadata,
                nodes={
                    'parameters': afm_params_file,
                    'ljff_data': ljff.FFLJ_npz,
                    'hartree_data': hartree_task.remote_folder,
                },
                filenames={
                    'hartree_data': 'hartree',
                },
                arguments=[
                    '-i',
                    'hartree/aiida.fileout',
                    '-F',
                    'cube',
                    '-f',
                    'npy',
                ],
                outputs=['FFel.npz'],
            )

            scan_nodes['elff_data'] = elff.FFel_npz

        # Experimental feature, not fully tested
        elif case == AfmCase.HARTREE_RHO.name:
            charge_params = pp_params.get('charge_density', {})
            assert charge_params, 'Missing charge density post-processing parameters'
            rho_job = PpJob(
                engine=engine,
                parent_folder=dft_job.remote_folder,
                parameters=charge_params,
            )

            assert tip, 'Missing tip structure'
            tip_dft_params = dft_params.get('tip', {})
            assert tip_dft_params, 'Missing tip DFT parameters'
            tip_dft_job = DftJob(
                engine=engine,
                structure=tip,
                parameters=tip_dft_params,
            )

            tip_rho_job = PpJob(
                engine=engine,
                parent_folder=tip_dft_job.remote_folder,
                parameters=charge_params,
            )

            conv_rho = shelljob(
                command='ppafm-conv-rho',
                nodes={
                    'geom_density': rho_job.remote_folder,
                    'tip_density': tip_rho_job.remote_folder,
                },
                filenames={
                    'geom_density': 'structure',
                    'tip_density': 'tip',
                },
                arguments=[
                    '-s',
                    'structure/aiida.fileout',
                    '-t',
                    'tip/aiida.fileout',
                    '-B',
                    '1.0',
                    '-E',
                ],
            )

            charge_elff = shelljob(
                command='ppafm-generate-elff',
                nodes={
                    'conv_rho_data': conv_rho.remote_folder,
                    'hartree_data': hartree_task.remote_folder,
                    'tip_density': tip_rho_job.remote_folder,
                },
                filenames={
                    'conv_rho_data': 'conv_rho',
                    'hartree_data': 'hartree',
                    'tip_density': 'tip',
                },
                arguments=[
                    '-i',
                    'hartree/aiida.fileout',
                    '-tip-dens',
                    'tip/aiida.fileout',
                    '--Rcode',
                    '0.7',
                    '-E',
                    '--doDensity',
                ],
                outputs=['FFel.npz'],
            )

            dftd3 = shelljob(
                command='ppafm-generate-dftd3',
                nodes={
                    'hartree_data': hartree_task.remote_folder,
                },
                filenames={
                    'hartree_data': 'hartree',
                },
                arguments=[
                    '-i',
                    'hartree/aiida.fileout',
                    '--df_name',
                    'PBE',
                ],
            )

            elff = shelljob(
                command='ppafm-generate-elff',
                nodes={
                    'hartree_data': hartree_task.remote_folder,
                    'charge_elff_data': charge_elff.FFel_npz,
                },
                filenames={
                    'hartree_data': 'hartree',
                },
                arguments=[
                    '-i',
                    'hartree/aiida.fileout',
                    '-f',
                    'npy',
                ],
                outputs=['FFel.npz'],
            )

        else:
            raise ValueError(f'Unsupported case: {case}')

    scan = shelljob(
        command='ppafm-relaxed-scan',
        metadata=metadata,
        nodes=scan_nodes,
        arguments=[
            '-f',
            'npy',
        ],
        outputs=['Q0.00K0.35'],
    )

    results = shelljob(
        command='ppafm-plot-results',
        metadata=metadata,
        nodes={
            'parameters': afm_params_file,
            'scan_dir': scan.Q0_00K0_35,
        },
        filenames={
            'scan_dir': 'Q0.00K0.35',
        },
        arguments=[
            '--df',
            '--cbar',
            '--save_df',
            '-f',
            'npy',
        ],
        outputs=['Q0.00K0.35'],
    )

    return results
