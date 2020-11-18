# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for Orca."""

import os
from typing import Any, Dict, List
from copy import deepcopy
import yaml

from aiida import engine
from aiida import orm
from aiida.plugins import DataFactory

from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('OrcaRelaxInputsGenerator',)

StructureData = DataFactory('structure')


class OrcaRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `OrcaRelaxWorkChain`."""

    _default_protocol = 'moderate'

    _calc_types = {'relax': {'code_plugin': 'orca_main', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.NONE: 'Single Point Calculation',
        RelaxType.ATOMS: 'Relaxing the geometry of molecule',
    }
    _spin_types = {
        SpinType.NONE: 'Restricted Kohn-Sham Calculation',
        SpinType.COLLINEAR: 'Unrestricted Kohn-Sham Calculation',
    }
    _electronic_types = {ElectronicType.METAL: 'ignored', ElectronicType.INSULATOR: 'ignored'}

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""

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

    def get_builder( # pylint: disable=too-many-branches
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

        # Checks
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        if 'relax' not in calc_engines:
            raise ValueError('The `calc_engines` dictionaly must contain "relaxation" as outermost key')

        if magnetization_per_site is not None:
            print('Warning: magnetization_per_site not supported, ignoring it.')

        params = self._get_params(protocol)

        # Delete optimization related keywords if it is a single point calculation
        if relax_type == RelaxType.NONE:
            inp_keywords = deepcopy(params['input_keywords'])
            new_inp_keywords = []
            for item in inp_keywords:
                if 'opt' not in item.lower():
                    new_inp_keywords.append(item)
            params['input_keywords'] = new_inp_keywords

        if spin_type == SpinType.COLLINEAR:
            params = params['input_keywords'].append('UKS')

        # Handle charge and multiplicity
        strc_pmg = structure.get_pymatgen_molecule()
        params['charge'] = int(strc_pmg.charge)
        params['multiplicity'] = strc_pmg.spin_multiplicity

        # Handle resources
        resources = calc_engines['relax']['options']['resources']
        nproc = None
        if 'tot_num_mpiprocs' in resources:
            nproc = resources['tot_num_mpiprocs']
        elif 'num_machines' in resources:
            if 'num_mpiprocs_per_machine' in resources:
                nproc = resources['num_machines'] * resources['num_mpiprocs_per_machine']
            else:
                code = orm.load_code(calc_engines['relax']['code'])
                default_mpiprocs = code.computer.get_default_mpiprocs_per_machine()
                if default_mpiprocs is not None:
                    nproc = resources['num_machines'] * default_mpiprocs

        if nproc is not None:
            params['input_blocks']['pal'] = {'nproc': nproc}

        builder = self.process_class.get_builder()
        builder.orca.structure = structure
        builder.orca.parameters = orm.Dict(dict=params)
        builder.orca.code = orm.load_code(calc_engines['relax']['code'])
        builder.orca.metadata.options = calc_engines['relax']['options']
        return builder

    def _get_params(self, key):
        return self._protocols[key]


#EOF
