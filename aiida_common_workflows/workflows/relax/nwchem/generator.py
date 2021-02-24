# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for NWChem."""
from typing import Any, Dict, List
import pathlib
import warnings
import yaml

import numpy as np

from aiida import engine
from aiida import orm
from aiida import plugins

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('NwchemRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')

HA_BOHR_TO_EV_A = 51.42208619083232


class NwchemRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `NwchemRelaxWorkChain`."""

    _default_protocol = 'moderate'

    _calc_types = {'relax': {'code_plugin': 'nwchem.nwchem', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.',
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
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
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

        # Protocol
        parameters = self.get_protocol(protocol)
        _ = parameters.pop('description')
        _ = parameters.pop('name')

        # kpoints
        target_spacing = parameters.pop('kpoint_spacing')
        reciprocal_axes_lengths = np.linalg.norm(np.linalg.inv(structure.cell), axis=1)
        kpoints = np.ceil(reciprocal_axes_lengths / target_spacing).astype(int).tolist()
        parameters['nwpw']['monkhorst-pack'] = '{} {} {}'.format(*kpoints)

        # Relaxation type
        if relax_type == RelaxType.ATOMS:
            parameters['task'] = 'band optimize'
        elif relax_type == RelaxType.ATOMS_CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.'}
        elif relax_type == RelaxType.CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.', 'nwpw:zero_forces': '.true.'}
        elif relax_type == RelaxType.NONE:
            parameters['task'] = 'band gradient'
            _ = parameters.pop('driver')
        else:
            raise ValueError('relax_type `{}` is not supported'.format(relax_type.value))

        # Electronic type
        if electronic_type == ElectronicType.INSULATOR:
            pass
        elif electronic_type == ElectronicType.METAL:
            parameters['nwpw']['smear'] = 'fermi'
            parameters['nwpw']['scf'] = 'Anderson outer_iterations 0 Kerker 2.0'
            parameters['nwpw']['loop'] = '10 10'
            _ = parameters['nwpw'].pop('lmbfgs')  # Revert to CG
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

        # Special case of a molecule in "open boundary conditions"
        if structure.pbc == (False, False, False):
            warnings.warn('PBCs set to false in input structure: assuming this is a molecular calculation')
            parameters['nwpw']['monkhorst-pack'] = '1 1 1'  # Gamma only
            parameters['nwpw']['cutoff'] = 250

        # Forces threshold.
        if threshold_forces is not None:
            parameters['driver']['xmax'] = '{}'.format(threshold_forces / HA_BOHR_TO_EV_A)

        # Stress threshold.
        if threshold_stress is not None:
            raise ValueError('Overall stress is not used as a stopping criterion in NWChem')

        # Prepare builder
        builder = self.process_class.get_builder()

        builder.nwchem.code = orm.load_code(calc_engines['relax']['code'])
        builder.nwchem.metadata.options = calc_engines['relax']['options']
        builder.nwchem.parameters = orm.Dict(dict=parameters)
        builder.nwchem.add_cell = orm.Bool(True)
        builder.nwchem.structure = structure

        return builder
