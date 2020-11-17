# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for FLEUR."""
import collections
import pathlib
from typing import Any, Dict, List
import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from ..generator import RelaxInputsGenerator, RelaxType, SpinType, ElectronicType

__all__ = ('FleurRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')


class FleurRelaxInputsGenerator(RelaxInputsGenerator):
    """Generator of inputs for the `FleurRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols = {
        'fast': {
            'description': 'return in a quick way a result that may not be reliable'
        },
        'moderate': {
            'description': 'reliable result (could be published), but no emphasis on convergence'
        },
        'precise': {
            'description': 'high level of accuracy'
        }
    }

    _calc_types = {
        'relax': {
            'code_plugin': 'fleur.fleur',
            'description': 'The code to perform the relaxation.'
        },
        'inpgen': {
            'code_plugin': 'fleur.inpgen',
            'description': 'The code to generate the input files for FLEUR.'
        }
    }

    _relax_types = {
        RelaxType.NONE: 'Do not relax forces, just run a SCF workchain.',
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.'
        # RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
        # currently not supported by Fleur
    }
    _spin_types = {
        SpinType.NONE: 'Non magnetic calculation, forcefully switch it off in FLEUR.',
        SpinType.COLLINEAR: 'Magnetic calculation with collinear spins'
    }
    _electronic_types = {
        ElectronicType.METAL: 'For FLEUR, metals and insulators are equally treated',
        ElectronicType.INSULATOR: 'For FLEUR, metals and insulators are equally treated'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the inputs generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml')) as handle:
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
        # pylint: disable=too-many-locals

        inpgen_code = calc_engines['inpgen']['code']
        fleur_code = calc_engines['relax']['code']
        if not isinstance(inpgen_code, orm.Code):
            inpgen_code = orm.load_code(inpgen_code)
        if not isinstance(fleur_code, orm.Code):
            fleur_code = orm.load_code(fleur_code)

        # Checks if protocol exists
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        else:
            protocol = self.get_protocol(protocol)

        builder = self.process_class.get_builder()

        if threshold_forces is not None:
            # Fleur expects atomic units i.e Hartree/bohr
            conversion_fac = 51.421
            force_criterion = threshold_forces / conversion_fac
        else:
            force_criterion = 0.001

        if threshold_stress is not None:
            pass  # Stress is not supported

        film_relax = not structure.pbc[-1]

        default_wf_para = {
            'relax_iter': 5,
            'film_distance_relaxation': film_relax,
            'force_criterion': force_criterion,
            'change_mixing_criterion': 0.025,
            'atoms_off': [],
            'run_final_scf': True  # we always run a final scf after the relaxation
        }
        wf_para_dict = recursive_merge(default_wf_para, protocol.get('relax', {}))

        parameters = None

        # Relax type options
        if relax_type == RelaxType.ATOMS:
            relaxation_mode = 'force'
        elif relax_type == RelaxType.NONE:
            relaxation_mode = 'force'
            wf_para_dict['relax_iter'] = 0
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relax_type.value))

        wf_para = orm.Dict(dict=wf_para_dict)

        default_scf = {
            'fleur_runmax': 2,
            'itmax_per_run': 120,
            'force_converged': force_criterion,
            'force_dict': {
                'qfix': 2,
                'forcealpha': 0.75,
                'forcemix': 'straight'
            },
            'use_relax_xml': True,
            'serial': False,
            'mode': relaxation_mode,
        }
        protocol_scf_para = protocol.get('scf', {})
        kmax = protocol_scf_para.pop('k_max_cutoff', None)

        wf_para_scf_dict = recursive_merge(default_scf, protocol_scf_para)
        wf_para_scf = orm.Dict(dict=wf_para_scf_dict)

        if previous_workchain is not None:
            parameters = get_parameters(previous_workchain)

        # User specification overrides previous workchain!
        if 'calc_parameters' in kwargs.keys():
            parameters = kwargs.pop('calc_parameters')

        parameters = prepare_calc_parameters(parameters, spin_type, magnetization_per_site, kmax)

        inputs = {
            'scf': {
                'wf_parameters': wf_para_scf,
                'structure': structure,
                'calc_parameters': parameters,
                # 'options': options_scf,
                # options do not matter on QM, in general they do...
                'inpgen': inpgen_code,
                'fleur': fleur_code
            },
            'wf_parameters': wf_para
        }

        builder._update(inputs)  # pylint: disable=protected-access

        return builder


def prepare_calc_parameters(parameters, spin_type, magnetization_per_site, kmax):
    """Prepare a calc_parameter node for a inpgen jobcalc

    Depending on the imports merge information

    :param parameters: given calc_parameter orm.Dict node to merge with
    :param spin_type: type of magnetic calculation
    :param magnetization_per_site: list
    :param kmax: int, basis cutoff for the simulations
    :return: orm.Dict
    """
    # Spin type options
    if spin_type == SpinType.NONE:
        jspins = 1
    else:
        jspins = 2
    add_parameter_dict = {'comp': {'jspins': jspins}}

    if magnetization_per_site is not None:
        if spin_type == SpinType.NONE:
            import warnings
            warnings.warn('`magnetization_per_site` will be ignored as `spin_type` is set to SpinType.NONE')
        if spin_type == SpinType.COLLINEAR:
            pass
            # add atom lists for each kind and set bmu
            # this will break symmetry
            # be careful here because this may override things the plugin is during already.

    # electronic Structure options
    # None. Gff we want to increase the smearing and kpoint density in case of metal

    if kmax is not None:  # add kmax from protocol
        add_parameter_dict = recursive_merge(add_parameter_dict, {'comp': {'kmax': kmax}})

    if parameters is not None:
        add_parameter_dict = recursive_merge(add_parameter_dict, parameters.get_dict())
        # In general better use aiida-fleur merge methods for calc parameters...

    new_parameters = orm.Dict(dict=add_parameter_dict)

    return new_parameters


def get_parameters(previous_workchain):
    """
    Extracts the FLAPW parameter for inpgen from a given previous workchain
    It finds the last Fleur Calcjob or Inpgen calc and extracts the
    parameters from its fleurinpdata node
    :param previous_workchain: Some workchain which contains at least one
                               Fleur CalcJob or Inpgen CalcJob.
    :return: Dict node of parameters ready to use, or None
    """
    from aiida.plugins import WorkflowFactory
    from aiida.common.exceptions import NotExistent
    from aiida_fleur.tools.common_fleur_wf import find_last_submitted_workchain

    fleur_scf_wc = WorkflowFactory('fleur.scf')
    # Find Fleurinp
    try:
        last_base_relax = find_last_submitted_workchain(previous_workchain)
        last_relax = find_last_submitted_workchain(orm.load_node(last_base_relax))
        last_scf = find_last_submitted_workchain(orm.load_node(last_relax))
        last_scf = orm.load_node(last_scf)
    except NotExistent:
        # something went wrong in the previous workchain run
        #.. we just continue without previous parameters but defaults.
        return None
    if last_scf.process_class is fleur_scf_wc:
        fleurinp = last_scf.outputs.fleurinp
    else:
        return None
    # Be aware that this parameter node is incomplete. LOs and econfig is
    # currently missing for example.
    parameters = fleurinp.get_parameterdata_ncf()  # This is not a calcfunction!
    return parameters


# Same code as in Quantum_espresso generator.py could be moved somewhere else and imported
def recursive_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries into a single dictionary.

    :param left: first dictionary.
    :param right: second dictionary.
    :return: the recursively merged dictionary.
    """
    for key, value in left.items():
        if key in right:
            if isinstance(value, collections.Mapping) and isinstance(right[key], collections.Mapping):
                right[key] = recursive_merge(value, right[key])

    merged = left.copy()
    merged.update(right)

    return merged
