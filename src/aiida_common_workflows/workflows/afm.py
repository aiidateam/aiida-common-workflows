from __future__ import annotations

import re
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


def _scan_output_label(afm_params: dict[str, t.Any]) -> str:
    """Return ppafm scan output directory label derived from Q and K values."""
    charge = float(afm_params.get('charge', 0.0))
    klat = float(afm_params.get('klat', 0.35))
    return f'Q{charge:.2f}K{klat:.2f}'


def _output_label_to_attr(label: str) -> str:
    """Translate shelljob output label to the generated attribute name."""
    return re.sub(r'\W', '_', label)


def _plain(value: t.Any) -> t.Any:
    return value.value if hasattr(value, 'value') else value


@task
def write_afm_params(params: dict) -> orm.SinglefileData:
    with TemporaryDirectory() as tmpdir:
        afm_filepath = Path(tmpdir) / 'params.ini'
        with open(afm_filepath, 'w') as config_file:
            for key, param_value in params.items():
                if isinstance(param_value, (list, tuple)):
                    rendered_value = ' '.join(map(str, param_value))
                else:
                    rendered_value = param_value
                config_file.write(f'{key} {rendered_value}\n')
        return orm.SinglefileData(file=afm_filepath.as_posix())


@task
def write_structure_file(structure: Atoms, filename: str) -> orm.SinglefileData:
    with TemporaryDirectory() as tmpdir:
        geom_filepath = Path(tmpdir) / filename
        structure.write(geom_filepath, format='xyz')
        return orm.SinglefileData(file=geom_filepath.as_posix())


@task.graph(
    inputs=namespace(
        engine=str,
        structure=orm.StructureData,
        engines=namespace(
            relax=namespace(
                code=orm.Code,
                options=dict,
            ),
        ),
        protocol=str,
        relax_type=str,
    ),
    outputs=namespace(
        relaxed_structure=orm.StructureData,
        forces=orm.ArrayData,
        stress=orm.ArrayData,
        trajectory=orm.TrajectoryData,
        total_energy=orm.Float,
        total_magnetization=orm.Float,
        remote_folder=orm.RemoteData,
    ),
)
def ScfJob(
    engine: str,
    structure: orm.StructureData,
    engines: dict,
    protocol: str,
    relax_type: str,
) -> t.Any:
    workflow = WorkflowFactory(f'common_workflows.relax.{_plain(engine)}')
    input_generator = workflow.get_input_generator()
    engines['relax']['options'] = _plain(engines['relax']['options'])
    builder = input_generator.get_builder(
        structure=structure,
        engines=engines,
        protocol=_plain(protocol),
        relax_type=_plain(relax_type),
    )
    return task(builder._process_class)(**get_dict_from_builder(builder))


@task.graph(
    inputs=namespace(
        engine=str,
        parent_folder=orm.RemoteData,
        engines=namespace(
            pp=namespace(
                code=orm.Code,
                options=dict,
            ),
        ),
        quantity=str,
    ),
    outputs=namespace(
        remote_folder=orm.RemoteData,
        quantity=orm.ArrayData,
    ),
)
def PpJob(
    engine: str,
    parent_folder: orm.RemoteData,
    engines: dict,
    quantity: str,
) -> orm.RemoteData:
    workflow = WorkflowFactory(f'common_workflows.pp.{_plain(engine)}')
    input_generator = workflow.get_input_generator()
    engines['pp']['options'] = _plain(engines['pp']['options'])
    builder = input_generator.get_builder(
        parent_folder=parent_folder,
        engines=engines,
        quantity=_plain(quantity),
    )
    return task(builder._process_class)(**get_dict_from_builder(builder))


@task.graph(
    inputs=namespace(
        engine=str,
        case=AfmCase,
        structure=orm.StructureData,
        afm_params=dict,
        scf_params=namespace(
            engines=namespace(
                relax=namespace(
                    code=orm.Code,
                    options=dict,
                ),
            ),
            protocol=str,
            structure=namespace(
                relax_type=str,
            ),
            tip=namespace(
                relax_type=str,
            ),
        ),
        pp_params=namespace(
            engines=namespace(
                pp=namespace(
                    code=orm.Code,
                    options=dict,
                ),
            ),
        ),
        tip=orm.StructureData,
    ),
    outputs=namespace(
        afm_scan=orm.FolderData,
    ),
)
def AfmWorkflow(
    engine: str,
    case: AfmCase,
    structure: orm.StructureData,
    afm_params: dict,
    scf_params: dict | None = None,
    pp_params: dict | None = None,
    tip: orm.StructureData = None,
) -> t.Any:
    """AFM simulation workflow."""
    should_relax_structure = scf_params and scf_params['structure']['relax_type'] != 'none'

    if should_relax_structure:
        assert scf_params, 'Missing SCF parameters'
        scf_job = ScfJob(
            engine=engine,
            structure=structure,
            engines=scf_params['engines'],
            protocol=scf_params['protocol'],
            relax_type=scf_params['structure']['relax_type'],
        )
        structure = scf_job.relaxed_structure
    else:
        assert structure, 'Missing structure'

    geometry_file = write_structure_file(structure, 'geo.xyz').result

    assert afm_params, 'Missing AFM parameters'
    afm_params_file = write_afm_params(params=afm_params).result

    ljff = shelljob(
        command='ppafm-generate-ljff',
        name='ljff',
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
        if not should_relax_structure:
            assert scf_params, 'Missing SCF parameters'
            scf_job = ScfJob(
                engine=engine,
                structure=structure,
                engines=scf_params['engines'],
                protocol=scf_params['protocol'],
                relax_type=scf_params['structure']['relax_type'],
            )

        assert pp_params, 'Missing post-processing parameters'
        hartree_task = PpJob(
            engine=engine,
            parent_folder=scf_job.remote_folder,
            engines=pp_params['engines'],
            quantity='potential',
        )

        if case == AfmCase.HARTREE.name:
            elff = shelljob(
                name='elff',
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
            rho_job = PpJob(
                engine=engine,
                parent_folder=scf_job.remote_folder,
                engines=pp_params['engines'],
                quantity='charge_density',
            )

            assert tip, 'Missing tip structure'
            tip_dft_job = ScfJob(
                engine=engine,
                structure=tip,
                engines=scf_params['engines'],
                protocol=scf_params['protocol'],
                relax_type=scf_params['tip']['relax_type'],
            )

            tip_rho_job = PpJob(
                engine=engine,
                parent_folder=tip_dft_job.remote_folder,
                engines=pp_params['engines'],
                quantity='charge_density',
            )

            conv_rho = shelljob(
                name='conv_rho',
                command='ppafm-conv-rho',
                nodes={
                    'structure_density': rho_job.remote_folder,
                    'tip_density': tip_rho_job.remote_folder,
                },
                filenames={
                    'structure_density': 'structure',
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

            # TODO add support for DFT-D3 dispersion correction
            # dftd3 = shelljob(
            #     command='ppafm-generate-dftd3',
            #     nodes={
            #         'hartree_data': hartree_task.remote_folder,
            #     },
            #     filenames={
            #         'hartree_data': 'hartree',
            #     },
            #     arguments=[
            #         '-i',
            #         'hartree/aiida.fileout',
            #         '--df_name',
            #         'PBE',
            #     ],
            # )

            elff = shelljob(
                name='elff',
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

    scan_output = _scan_output_label(afm_params)

    scan = shelljob(
        command='ppafm-relaxed-scan',
        name='scan',
        metadata=metadata,
        nodes=scan_nodes,
        arguments=[
            '-f',
            'npy',
        ],
        outputs=[scan_output],
    )

    results = shelljob(
        command='ppafm-plot-results',
        name='plot',
        metadata=metadata,
        nodes={
            'parameters': afm_params_file,
            'scan_dir': getattr(scan, _output_label_to_attr(scan_output)),
        },
        filenames={
            'scan_dir': scan_output,
        },
        arguments=[
            '--df',
            '--cbar',
            '--save_df',
            '-f',
            'npy',
        ],
        outputs=[scan_output],
    )

    return {
        'afm_scan': getattr(results, _output_label_to_attr(scan_output)),
    }
