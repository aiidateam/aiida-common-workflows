# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for CP2K."""
import collections
import pathlib
from typing import Any, Dict, List
import yaml

from aiida import engine
from aiida import orm
from aiida import plugins

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('Cp2kRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')

EV_A3_TO_GPA = 160.21766208


def dict_merge(dct, merge_dct):
    """ Taken from https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k in merge_dct.keys():
        if (k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def get_kinds_section(structure: StructureData):
    """ Write the &KIND sections given the structure and the settings_dict"""
    kinds = []
    with open(pathlib.Path(__file__).parent / 'atomic_kinds.yml') as handle:
        atom_data = yaml.safe_load(handle)
    all_atoms = set(structure.get_ase().get_chemical_symbols())
    for atom in all_atoms:
        kinds.append({
            '_': atom,
            'BASIS_SET': atom_data['basis_set'][atom],
            'POTENTIAL': atom_data['pseudopotential'][atom],
            'MAGNETIZATION': atom_data['initial_magnetization'][atom],
        })
    return {'FORCE_EVAL': {'SUBSYS': {'KIND': kinds}}}


def get_file_section():
    """Provide necessary parameter files such as pseudopotientials, basis sets, etc."""
    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT', 'rb') as handle:
        basis = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'BASIS_MOLOPT_UCL', 'rb') as handle:
        basis_ucl = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'GTH_POTENTIALS', 'rb') as handle:
        potential = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'dftd3.dat', 'rb') as handle:
        dftd3_params = orm.SinglefileData(file=handle)

    with open(pathlib.Path(__file__).parent / 'xTB_parameters', 'rb') as handle:
        xtb_params = orm.SinglefileData(file=handle)

    return {
        'basis': basis,
        'basis_ucl': basis_ucl,
        'potential': potential,
        'dftd3_params': dftd3_params,
        'xtb_dat': xtb_params,
    }


class Cp2kRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `Cp2kRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'cp2k', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
    }
    _spin_types = {SpinType.NONE: '....', SpinType.COLLINEAR: '....'}
    _electronic_types = {ElectronicType.METAL: '....', ElectronicType.INSULATOR: '....'}

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(pathlib.Path(__file__).parent / 'protocol.yml') as handle:
            self._protocols = yaml.safe_load(handle)

    def get_builder(
        self,
        structure: StructureData,
        calc_engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: RelaxType = RelaxType.ATOMS,
        electronic_type: ElectronicType = ElectronicType.METAL,
        spin_type: SpinType = SpinType.NONE,
        magnetization_per_site: List[float] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        previous_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param calc_engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param previous_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            calc_engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            previous_workchain=previous_workchain,
            **kwargs
        )

        # The builder.
        builder = self.process_class.get_builder()

        # Switch on the resubmit_unconverged_geometry which is disabled by default.
        builder.handler_overrides = orm.Dict(dict={'resubmit_unconverged_geometry': True})

        builder.cp2k.file = get_file_section()

        # Input structure.
        builder.cp2k.structure = structure

        # Input parameters.
        parameters = self.get_protocol(protocol)

        ## Removing description.
        _ = parameters.pop('description')

        kinds_section = get_kinds_section(builder.cp2k.structure)
        dict_merge(parameters, kinds_section)

        ## Relaxation type.
        if relax_type == RelaxType.ATOMS:
            run_type = 'GEO_OPT'
        elif relax_type == RelaxType.ATOMS_CELL:
            run_type = 'CELL_OPT'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))
        parameters['GLOBAL'] = {'RUN_TYPE': run_type}

        ## Redefining forces threshold.
        if threshold_forces is not None:
            parameters['MOTION'][run_type]['MAX_FORCE'] = '[eV/angstrom] {}'.format(threshold_forces)

        ## Redefining stress threshold.
        if threshold_stress is not None:
            parameters['MOTION']['CELL_OPT']['PRESSURE_TOLERANCE'] = '[GPa] {}'.format(threshold_stress * EV_A3_TO_GPA)
        builder.cp2k.parameters = orm.Dict(dict=parameters)

        # Additional files to be retrieved.
        builder.cp2k.settings = orm.Dict(dict={'additional_retrieve_list': ['aiida-frc-1.xyz', 'aiida-1.stress']})

        # CP2K code.
        builder.cp2k.code = orm.load_code(calc_engines['relax']['code'])

        # Run options.
        builder.cp2k.metadata.options = calc_engines['relax']['options']

        return builder
