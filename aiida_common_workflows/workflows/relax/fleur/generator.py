# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for FLEUR."""
import collections
import pathlib
from typing import Any, Dict
import yaml
from aiida import orm
from aiida.orm import Code, load_node
from ..generator import RelaxInputsGenerator, RelaxType, SpinType

__all__ = ('FleurRelaxInputsGenerator',)


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
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.'
        # RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
        # currently not supported by Fleur
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
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
        previous_workchain=None,
        is_insulator=False,
        spin=SpinType.NONE,
        initial_magnetization='auto',
        **kwargs
    ):
        """Return a process builder for the corresponding workchain class with
           inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param previous_workchain: AiiDA workchain node from which information can be extracted
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        from aiida.orm import load_code

        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            is_insulator, spin, initial_magnetization, **kwargs
        )

        # pylint: disable=too-many-locals
        inpgen_code = calc_engines['inpgen']['code']
        fleur_code = calc_engines['relax']['code']
        if not isinstance(inpgen_code, Code):
            inpgen_code = load_code(inpgen_code)
        if not isinstance(fleur_code, Code):
            fleur_code = load_code(fleur_code)

        # Checks if protocol exists
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        else:
            protocol = self.get_protocol(protocol)

        builder = self.process_class.get_builder()

        # implement this, protocol dependent, we still have option keys as nodes ...
        # has to go over calc parameters, kmax, lmax, kpoint density
        # inputs = generate_scf_inputs(process_class, protocol, code, structure)

        if relaxation_type == RelaxType.ATOMS:
            relaxation_mode = 'force'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

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

        wf_para_scf_dict = recursive_merge(default_scf, protocol.get('scf', {}))
        wf_para_scf = orm.Dict(dict=wf_para_scf_dict)

        inputs = {
            'scf': {
                'wf_parameters': wf_para_scf,
                'structure': structure,
                # 'calc_parameters': parameters, # protocol depended
                # 'options': options_scf,
                # options do not matter on QM, in general they do...
                'inpgen': inpgen_code,
                'fleur': fleur_code
            },
            'wf_parameters': wf_para
        }

        if previous_workchain is not None:
            parameters = get_parameters(previous_workchain)
            inputs['scf']['calc_parameters'] = parameters

        # User specification overrides previous workchain!
        if 'calc_parameters' in kwargs.keys():
            parameters = kwargs.pop('calc_parameters')
            inputs['scf']['calc_parameters'] = parameters

        builder._update(inputs)  # pylint: disable=protected-access

        return builder


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
        last_relax = find_last_submitted_workchain(load_node(last_base_relax))
        last_scf = find_last_submitted_workchain(load_node(last_relax))
        last_scf = load_node(last_scf)
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
