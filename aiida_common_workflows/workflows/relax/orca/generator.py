# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Orca."""
import os
from typing import Any, Dict, List, Tuple, Union
from copy import deepcopy
import warnings

import numpy as np
import yaml

from aiida import engine
from aiida import orm
from aiida.plugins import DataFactory

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('OrcaCommonRelaxInputGenerator',)

StructureData = DataFactory('structure')


class OrcaCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `OrcaCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    _engine_types = {'relax': {'code_plugin': 'orca_main', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'Single Point Calculation',
        RelaxType.POSITIONS: 'Relaxing the geometry of molecule',
    }
    _spin_types = {
        SpinType.NONE: 'Restricted Kohn-Sham Calculation',
        SpinType.COLLINEAR: 'Unrestricted Kohn-Sham Calculation',
    }
    _electronic_types = {ElectronicType.METAL: 'ignored', ElectronicType.INSULATOR: 'ignored'}

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError('invalid protocol registry `{}`: '.format(self.__class__.__name__) + message)

        for k, v in self._protocols.items():  # pylint: disable=invalid-name

            if 'input_keywords' not in v:
                raise_invalid('protocol `{}` does not define the mandatory key `input_keywords`'.format(k))

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        yamlpath = os.path.join(os.path.dirname(__file__), 'protocols.yaml')

        with open(yamlpath) as handler:
            self._protocols = yaml.safe_load(handler)

    def get_builder( # pylint: disable=too-many-branches, too-many-statements
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
        # pylint: disable=too-many-locals
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

        # Checks
        if any(structure.get_attribute_many(['pbc1', 'pbc2', 'pbc2'])):
            warnings.warn('Warning: PBC detected in the input structure. It is not supported and thus is ignored.')

        if protocol not in self.get_protocol_names():
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        if 'relax' not in engines:
            raise ValueError('The `engines` dictionaly must contain "relax" as outermost key')

        params = self._get_params(protocol)

        # Delete optimization related keywords if it is a single point calculation
        if relax_type == RelaxType.NONE:
            inp_keywords = deepcopy(params['input_keywords'])
            new_inp_keywords = []
            for item in inp_keywords:
                if 'opt' not in item.lower():
                    new_inp_keywords.append(item)
            new_inp_keywords.append('EnGrad')
            params['input_keywords'] = new_inp_keywords

        # Handle charge and multiplicity
        strc_pmg = structure.get_pymatgen_molecule()
        num_electrons = strc_pmg.nelectrons

        if num_electrons % 2 == 1 and spin_type == SpinType.NONE:
            raise ValueError(f'Spin-restricted calculation does not support odd number of electrons ({num_electrons})')

        params['charge'] = int(strc_pmg.charge)
        spin_multiplicity = 1

        # Logic from Kristijan code in gaussian.
        if spin_type == SpinType.COLLINEAR:
            params['input_keywords'].append('UKS')

            if magnetization_per_site is None:
                multiplicity_guess = 1
            else:
                warnings.warn(
                    'Warning: magnetization_per_site site-resolved info is disregarded, only total spin is processed.'
                )
                # magnetization_per_site are in units of [Bohr magnetons] (*0.5 to get in [au])
                total_spin_guess = 0.5 * np.abs(np.sum(magnetization_per_site))
                multiplicity_guess = 2 * total_spin_guess + 1

            # in case of even/odd electrons, find closest odd/even multiplicity
            if num_electrons % 2 == 0:
                # round guess to nearest odd integer
                spin_multiplicity = int(np.round((multiplicity_guess - 1) / 2) * 2 + 1)
            else:
                # round guess to nearest even integer; 0 goes to 2
                spin_multiplicity = max([int(np.round(multiplicity_guess / 2) * 2), 2])

            if spin_multiplicity == 1:
                params['input_blocks']['scf']['STABPerform'] = True
                if 'EnGrad' in params['input_keywords']:
                    params['input_keywords'].remove('EnGrad')

        params['multiplicity'] = spin_multiplicity

        # Handle resources
        resources = engines['relax']['options']['resources']
        nproc = None
        if 'tot_num_mpiprocs' in resources:
            nproc = resources['tot_num_mpiprocs']
        elif 'num_machines' in resources:
            if 'num_mpiprocs_per_machine' in resources:
                nproc = resources['num_machines'] * resources['num_mpiprocs_per_machine']
            else:
                code = orm.load_code(engines['relax']['code'])
                default_mpiprocs = code.computer.get_default_mpiprocs_per_machine()
                if default_mpiprocs is not None:
                    nproc = resources['num_machines'] * default_mpiprocs

        if nproc is not None:
            params['input_blocks']['pal'] = {'nproc': nproc}

        builder = self.process_class.get_builder()
        builder.orca.structure = structure
        builder.orca.parameters = orm.Dict(dict=params)
        builder.orca.code = orm.load_code(engines['relax']['code'])
        builder.orca.metadata.options = engines['relax']['options']
        return builder

    def _get_params(self, key):
        return self._protocols[key]
