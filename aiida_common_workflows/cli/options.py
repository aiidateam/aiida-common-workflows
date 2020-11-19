# -*- coding: utf-8 -*-
"""Module with pre-defined options and defaults for CLI command parameters."""
import click

from aiida.cmdline.params import options, types
from aiida.cmdline.utils.decorators import with_dbenv
from aiida_common_workflows.workflows.relax import RelaxType, SpinType


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


def get_default_structures_path(name):  #pylint: disable=too-many-return-statements
    """
    Return the filepath for the few default strutures we run as test cases:
    silicon, aluminum, iron, ammonia_pyramidal, ammonia_planar, hydrogen_molecule
    and germanium_telluride
    """
    import os.path as op
    datapath = op.join(op.dirname(__file__), '../common/data')

    if name == 'silicon':
        return op.join(datapath, 'Si.cif')
    if name == 'aluminum':
        return op.join(datapath, 'Al.cif')
    if name == 'iron':
        return op.join(datapath, 'Fe.cif')
    if name == 'germanium_telluride':
        return op.join(datapath, 'GeTe.cif')
    if name == 'ammonia_pyramidal':
        return op.join(datapath, 'nh3_cone.xyz')
    if name == 'ammonia_planar':
        return op.join(datapath, 'nh3_flat.xyz')
    if name == 'hydrogen_molecule':
        return op.join(datapath, 'h2.xyz')


class StructureDataParamType(types.DataParamType):
    """CLI parameter type that can load `StructureData` from identifier or from a CIF file on disk."""

    def __init__(self):
        super().__init__(sub_classes=('aiida.data:structure',))

    @with_dbenv()
    def convert(self, value, param, ctx):
        """Attempt to interpret the value as a file first and if that fails try to load as a node."""
        from aiida.orm import StructureData, QueryBuilder

        list_defaults = [
            'silicon', 'aluminum', 'iron', 'ammonia_pyramidal', 'ammonia_planar', 'hydrogen_molecule',
            'germanium_telluride'
        ]

        if value in list_defaults:
            value = get_default_structures_path(value)

        try:
            return super().convert(value, param, ctx)
        except click.BadParameter:
            pass

        try:
            import ase.io
        except ImportError as exception:
            raise click.BadParameter(
                f'failed to load a structure with identifier `{value}`.\n'
                'Cannot parse from file because `ase` is not installed.'
            ) from exception

        try:
            filepath = click.Path(exists=True, dir_okay=False, resolve_path=True).convert(value, param, ctx)
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


STRUCTURE = options.OverridableOption(
    '-S',
    '--structure',
    type=StructureDataParamType(),
    default='silicon',
    help='A structure data node or a file on disk that can be parsed by `ase`.'
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
    callback=lambda ctx, value: RelaxType(value),
    help='Select the relax type with which the workflow should be run.'
)

SPIN_TYPE = options.OverridableOption(
    '-s',
    '--spin-type',
    type=types.LazyChoice(get_spin_types),
    default='none',
    show_default=True,
    callback=lambda ctx, value: SpinType(value),
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
