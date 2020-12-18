# -*- coding: utf-8 -*-
"""Module with pre-defined options and defaults for CLI command parameters."""
import pathlib

import click

from aiida.cmdline.params import options, types
from aiida.cmdline.utils.decorators import with_dbenv
from aiida_common_workflows.workflows.relax import RelaxType, SpinType

DEFAULT_STRUCTURES_MAPPING = {
    'Al': 'Al.cif',
    'Fe': 'Fe.cif',
    'GeTe': 'GeTe.cif',
    'Si': 'Si.cif',
    'NH3-pyramidal': 'nh3_cone.xyz',
    'NH3-planar': 'nh3_flat.xyz',
    'H2': 'h2.xyz',
}


def get_workchain_plugins():
    """Return the registered entry point names for the ``CommonRelaxWorkChain``."""
    from aiida.plugins import entry_point
    group = 'aiida.workflows'
    entry_point_prefix = 'common_workflows.relax.'
    names = entry_point.get_entry_point_names(group)
    return {name[len(entry_point_prefix):] for name in names if name.startswith(entry_point_prefix)}


def get_relax_types_eos():
    """Return the relaxation types available for the common equation of states workflow."""
    return [item.value for item in RelaxType if 'cell' not in item.value and 'volume' not in item.value]


def get_relax_types():
    """Return the relaxation types available for the common relax workflow."""
    return [entry.value for entry in RelaxType]


def get_spin_types():
    """Return the spin types available for the common relax workflow."""
    return [entry.value for entry in SpinType]


class StructureDataParamType(click.Choice):
    """CLI parameter type that can load `StructureData` from identifier or from a CIF file on disk."""

    def __init__(self):
        super().__init__(list(DEFAULT_STRUCTURES_MAPPING.keys()))

    @with_dbenv()
    def convert(self, value, param, ctx):
        """Attempt to interpret the value as a file first and if that fails try to load as a node."""
        from aiida.orm import StructureData, QueryBuilder

        try:
            filepath = pathlib.Path(__file__).parent.parent / 'common' / 'data' / DEFAULT_STRUCTURES_MAPPING[value]
        except KeyError:
            try:
                return types.DataParamType(sub_classes=('aiida.data:structure',)).convert(value, param, ctx)
            except click.BadParameter:
                filepath = value

        try:
            import ase.io
        except ImportError as exception:
            raise click.BadParameter(
                f'failed to load a structure with identifier `{value}`.\n'
                'Cannot parse from file because `ase` is not installed.'
            ) from exception

        try:
            filepath = click.Path(exists=True, dir_okay=False, resolve_path=True).convert(filepath, param, ctx)
        except click.BadParameter as exception:
            raise click.BadParameter(
                f'failed to load a structure with identifier `{value}` and it can also not be resolved as a file.'
            ) from exception

        try:
            structure = StructureData(ase=ase.io.read(filepath))
        except Exception as exception:  # pylint: disable=broad-except
            raise click.BadParameter(
                f'file `{value}` could not be parsed into a `StructureData`: {exception}'
            ) from exception

        duplicate = QueryBuilder().append(StructureData, filters={'extras._aiida_hash': structure._get_hash()}).first()  # pylint: disable=protected-access

        if duplicate:
            return duplicate[0]

        return structure


CODES = options.OverridableOption(
    '-X',
    '--codes',
    'codes',
    type=types.CodeParamType(),
    cls=options.MultipleValueOption,
    help='One or multiple codes identified by their ID, UUID or label. What codes are required is dependent on the '
    'selected plugin and can be shown using the `--show-engines` option. If no explicit codes are specified, one will '
    'be loaded from the database based on the required input plugins. If multiple codes are matched, a random one will '
    'be selected.'
)

STRUCTURE = options.OverridableOption(
    '-S',
    '--structure',
    type=StructureDataParamType(),
    default='Si',
    help='Select a structure: either choose one of the default structures listed above, or an existing `StructureData` '
    'identifier, or a file on disk with a structure definition that can be parsed by `ase`.'
)

PROTOCOL = options.OverridableOption(
    '-p',
    '--protocol',
    type=click.Choice(['fast', 'moderate', 'precise']),
    default='fast',
    show_default=True,
    help='Select the protocol with which the inputs for the workflow should be generated.'
)

RELAX_TYPE = options.OverridableOption(
    '-r',
    '--relax-type',
    type=types.LazyChoice(get_relax_types),
    default='atoms',
    show_default=True,
    callback=lambda ctx, param, value: RelaxType(value),
    help='Select the relax type with which the workflow should be run.'
)

SPIN_TYPE = options.OverridableOption(
    '-s',
    '--spin-type',
    type=types.LazyChoice(get_spin_types),
    default='none',
    show_default=True,
    callback=lambda ctx, param, value: SpinType(value),
    help='Select the spin type with which the workflow should be run.'
)

THRESHOLD_FORCES = options.OverridableOption(
    '--threshold-forces',
    type=click.FLOAT,
    required=False,
    help='Optional convergence threshold for the forces. Note that not all plugins may support this option.'
)

THRESHOLD_STRESS = options.OverridableOption(
    '--threshold-stress',
    type=click.FLOAT,
    required=False,
    help='Optional convergence threshold for the stress. Note that not all plugins may support this option.'
)

DAEMON = options.OverridableOption(
    '-d',
    '--daemon',
    is_flag=True,
    default=False,
    help='Submit the process to the daemon instead of running it locally.'
)

WALLCLOCK_SECONDS = options.OverridableOption(
    '-w',
    '--wallclock-seconds',
    cls=options.MultipleValueOption,
    metavar='VALUES',
    required=False,
    help='Define the wallclock seconds to request for each engine step.'
)

NUMBER_MACHINES = options.OverridableOption(
    '-m',
    '--number-machines',
    cls=options.MultipleValueOption,
    metavar='VALUES',
    required=False,
    help='Define the number of machines to request for each engine step.'
)

MAGNETIZATION_PER_SITE = options.OverridableOption(
    '--magnetization-per-site',
    type=click.FLOAT,
    cls=options.MultipleValueOption,
    required=False,
    help='Optional list containing the initial spin polarization per site in units of electrons.'
)

PRECISIONS = options.OverridableOption(
    '-p',
    '--precisions',
    cls=options.MultipleValueOption,
    type=click.INT,
    required=False,
    help='Specify the precision of floats used when printing them to stdout with the `--print-table` option.'
)

PRINT_TABLE = options.OverridableOption(
    '-t', '--print-table', is_flag=True, help='Print the volume and energy table instead of plotting.'
)

PREVIOUS_WORKCHAIN = options.OverridableOption(
    '-P',
    '--previous-workchain',
    type=types.WorkflowParamType(),
    required=False,
    help='An instance of a completed workchain of the same type as would be run for the given plugin.'
)
