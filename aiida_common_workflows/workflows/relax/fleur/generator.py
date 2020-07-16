# -*- coding: utf-8 -*-
"""
Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator`
for FLEUR.
"""
from aiida.orm import Dict, Code
from ..generator import RelaxInputsGenerator, RelaxType
from .workchain import FleurCRelaxWorkChain as FleurRelaxationWorkChain

__all__ = ('FleurRelaxInputsGenerator',)


class FleurRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `FleurCRelaxWorkChain`."""

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

    _calc_types = {'relax': {'code_plugin': 'fleur.fleur', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.'
        # RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
        # currently not supported by Fleur
    }

    def get_builder(
        self,
        structure,
        calc_engines,
        protocol,
        relaxation_type,
        threshold_forces=None,
        threshold_stress=None,
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
        :param kwargs: any inputs that are specific to the plugin.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        #from aiida_fleur.tools.common_wf_util import generate_scf_inputs

        fleur_code = Code.get_from_string(calc_engines['relax']['code'])
        inpgen_code = Code.get_from_string(calc_engines['relax']['inputgen'])
        process_class = FleurRelaxationWorkChain._process_class  # pylint: disable=protected-access

        builder = FleurRelaxationWorkChain.get_builder()

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

        if structure.pbc == (True, True, False):
            film_relax = True
        else:
            film_relax = False

        wf_para = Dict(
            dict={
                'relax_iter': 5,
                'film_distance_relaxation': film_relax,
                'force_criterion': force_criterion,
                'change_mixing_criterion': 0.025,
                'atoms_off': [],
                'run_final_scf': True  # we always run a final scf after the relaxation
            }
        )

        wf_para_scf = Dict(
            dict={
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
        )

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

        if 'calc_parameters' in kwargs.keys():
            parameters = kwargs.pop('calc_parameters')
            inputs['scf']['calc_parameters'] = parameters

        builder._update(inputs)  # pylint: disable=protected-access

        return builder
