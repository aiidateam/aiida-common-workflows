"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Orca."""
import os
import warnings
from copy import deepcopy

import numpy as np
import yaml
from aiida import engine, orm
from aiida.plugins import DataFactory

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('OrcaCommonRelaxInputGenerator',)

StructureData = DataFactory('core.structure')


class OrcaCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `OrcaCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError(f'invalid protocol registry `{self.__class__.__name__}`: ' + message)

        for k, v in self._protocols.items():
            if 'input_keywords' not in v:
                raise_invalid(f'protocol `{k}` does not define the mandatory key `input_keywords`')

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        yamlpath = os.path.join(os.path.dirname(__file__), 'protocol.yml')

        with open(yamlpath, encoding='utf-8') as handler:
            self._protocols = yaml.safe_load(handler)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE, RelaxType.POSITIONS))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('orca_main')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)

        # Checks
        if any(structure.base.attributes.get_many(['pbc1', 'pbc2', 'pbc2'])):
            warnings.warn('PBC detected in the input structure. It is not supported and thus is ignored.')

        if protocol not in self.get_protocol_names():
            warnings.warn(f'no protocol implemented with name {protocol}, using default moderate')
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
                warnings.warn('magnetization_per_site site-resolved info is disregarded, only total spin is processed.')
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
                code = engines['relax']['code']
                default_mpiprocs = code.computer.get_default_mpiprocs_per_machine()
                if default_mpiprocs is not None:
                    nproc = resources['num_machines'] * default_mpiprocs

        if nproc is not None:
            params['input_blocks']['pal'] = {'nproc': nproc}

        builder = self.process_class.get_builder()
        builder.orca.structure = structure
        builder.orca.parameters = orm.Dict(dict=params)
        builder.orca.code = engines['relax']['code']
        builder.orca.metadata.options = engines['relax']['options']
        return builder

    def _get_params(self, key):
        return self._protocols[key]
