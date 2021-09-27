# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for NWChem."""
from typing import Any, Dict, List, Tuple, Union
import pathlib
import warnings
import yaml

import numpy as np

from aiida import engine
from aiida import orm
from aiida import plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('NwchemCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')

HA_BOHR_TO_EV_A = 51.42208619083232


class NwchemCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `NwchemCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    _engine_types = {'relax': {'code_plugin': 'nwchem.nwchem', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.POSITIONS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.POSITIONS_CELL: 'Relax both atomic positions and the cell.',
        RelaxType.CELL: 'Relax only the cell.',
        RelaxType.NONE: 'An SCF calculation'
    }
    _spin_types = {
        SpinType.NONE: 'non-magnetic calculation',
        SpinType.COLLINEAR: 'magnetic calculation with collinear spin'
    }
    _electronic_types = {
        ElectronicType.METAL: 'a calculation with finite temperature smearing',
        ElectronicType.INSULATOR: 'a standard calculation with fixed occupations'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(pathlib.Path(__file__).parent / 'protocol.yml') as handle:
            self._protocols = yaml.safe_load(handle)

    def get_builder(
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: Union[RelaxType, str] = RelaxType.POSITIONS,
        electronic_type: Union[ElectronicType, str] = ElectronicType.METAL,
        spin_type: Union[SpinType, str] = SpinType.NONE,
        magnetization_per_site: Union[List[float], Tuple[float]] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed.
        :param engines: a dictionary containing the computational resources for the relaxation.
        :param protocol: the protocol to use when determining the workchain inputs.
        :param relax_type: the type of relaxation to perform.
        :param electronic_type: the electronic character that is to be used for the structure.
        :param spin_type: the spin polarization type to use for the calculation.
        :param magnetization_per_site: a list with the initial spin polarization for each site. Float or integer in
            units of electrons. If not defined, the builder will automatically define the initial magnetization if and
            only if `spin_type != SpinType.NONE`.
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param reference_workchain: a <Code>RelaxWorkChain node.
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        protocol = protocol or self.get_default_protocol_name()

        super().get_builder(
            structure,
            engines,
            protocol=protocol,
            relax_type=relax_type,
            electronic_type=electronic_type,
            spin_type=spin_type,
            magnetization_per_site=magnetization_per_site,
            threshold_forces=threshold_forces,
            threshold_stress=threshold_stress,
            reference_workchain=reference_workchain,
            **kwargs
        )

        if isinstance(electronic_type, str):
            electronic_type = ElectronicType(electronic_type)

        if isinstance(relax_type, str):
            relax_type = RelaxType(relax_type)

        if isinstance(spin_type, str):
            spin_type = SpinType(spin_type)

        # Protocol
        parameters = self.get_protocol(protocol)
        parameters.pop('description', None)
        parameters.pop('name', None)

        # # kpoints
        target_spacing = parameters.pop('kpoint_spacing')
        if reference_workchain:
            ref_kpoints = reference_workchain.inputs.nwchem__parameters['nwpw']['monkhorst-pack']
            parameters['nwpw']['monkhorst-pack'] = ref_kpoints
        else:
            reciprocal_axes_lengths = np.linalg.norm(np.linalg.inv(structure.cell), axis=1)
            kpoints = np.ceil(reciprocal_axes_lengths / target_spacing).astype(int).tolist()
            parameters['nwpw']['monkhorst-pack'] = '{} {} {}'.format(*kpoints)

        # Relaxation type
        if relax_type == RelaxType.POSITIONS:
            parameters['task'] = 'band optimize'
        elif relax_type == RelaxType.POSITIONS_CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.'}
        elif relax_type == RelaxType.CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.', 'nwpw:zero_forces': '.true.'}
        elif relax_type == RelaxType.NONE:
            parameters['task'] = 'band gradient'
            parameters.pop('driver', None)
        else:
            raise ValueError('relax_type `{}` is not supported'.format(relax_type.value))

        # Electronic type
        if electronic_type == ElectronicType.INSULATOR:
            pass
        elif electronic_type == ElectronicType.METAL:
            parameters['nwpw']['smear'] = 'fermi'
            parameters['nwpw']['scf'] = 'Anderson outer_iterations 0 Kerker 2.0'
            parameters['nwpw']['loop'] = '10 10'
            parameters['nwpw'].pop('lmbfgs', None)  # Revert to CG
        else:
            raise ValueError('electronic_type `{}` is not supported'.format(electronic_type.value))

        # Spin type
        if spin_type == SpinType.NONE:
            pass
        elif spin_type == SpinType.COLLINEAR:
            parameters['nwpw']['odft'] = ''
        else:
            raise ValueError('spin_type `{}` is not supported'.format(spin_type.value))

        # Magnetization per site
        # Not implemented yet - one has to specify the site, spin AND angular momentum
        if magnetization_per_site:
            raise ValueError('magnetization per site not yet supported')

        # Add a unit cell to the geometry stanza
        add_cell = orm.Bool(True)

        # Special case of a molecule in "open boundary conditions"
        if structure.pbc == (False, False, False):
            warnings.warn('PBCs set to false in input structure: assuming this is a molecular calculation')
            add_cell = orm.Bool(False)
            # We don't use the geometry stanza for the cell, but add it in the parameters
            parameters['nwpw']['simulation_cell angstroms'] = {
                'lattice': {
                    'lat_a': structure.cell_lengths[0],
                    'lat_b': structure.cell_lengths[1],
                    'lat_c': structure.cell_lengths[2],
                    'alpha': structure.cell_angles[0],
                    'beta': structure.cell_angles[1],
                    'gamma': structure.cell_angles[2],
                }
            }
            parameters['driver']['redoautoz'] = ''  # To ensure internal coordinates are refreshed
            parameters['nwpw']['cutoff'] = 140
            parameters['task'] = 'pspw optimize'

            parameters['nwpw'].pop('monkhorst-pack', None)
            parameters['nwpw'].pop('ewald_rcut', None)
            parameters['nwpw'].pop('ewald_ncut', None)
            parameters['nwpw'].pop('smear', None)
            parameters['nwpw'].pop('scf', None)
            parameters['nwpw'].pop('loop', None)

        # Forces threshold.
        if threshold_forces is not None:
            parameters['driver']['xmax'] = '{}'.format(threshold_forces / HA_BOHR_TO_EV_A)

        # Stress threshold.
        if threshold_stress is not None:
            raise ValueError('Overall stress is not used as a stopping criterion in NWChem')

        # Prepare builder
        builder = self.process_class.get_builder()
        builder.nwchem.code = orm.load_code(engines['relax']['code'])
        builder.nwchem.metadata.options = engines['relax']['options']
        builder.nwchem.structure = structure
        builder.nwchem.add_cell = add_cell
        builder.nwchem.parameters = orm.Dict(dict=parameters)

        return builder
