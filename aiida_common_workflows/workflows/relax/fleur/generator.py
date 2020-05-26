# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for FLEUR."""
from aiida import orm

from ..generator import RelaxInputsGenerator, RelaxType
from .workchain import FleurRelaxationWorkChain
from aiida.orm import Dict
__all__ = ('FleurRelaxInputsGenerator',)



class FleurRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `FleurRelaxWorkChain`."""

    _default_protocol = 'standard'
    _protocols = {'test': {'description': ''}, 'standard': {'description': ''}}

    _calc_types = {'relax': {'code_plugin': 'fleur.fleur', 'description': 'The code to perform the relaxation.'}}

    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        #RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.' # currently not supported
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
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :param kwargs: any inputs that are specific to the plugin.
        i:return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals
        #from aiida_fleur.tools.common_wf_util import generate_scf_inputs  # pylint: disable=import-error

        fleur_code = calc_engines['relax']['code']
        # TODO: maybe other way to get inpgen?
        inpgen_code = kwargs.pop('inpgen') #calc_engines['relax']['inpgen']
        process_class = FleurRelaxationWorkChain._process_class  # pylint: disable=protected-access

        builder = FleurRelaxationWorkChain.get_builder()

        # TODO implement this, protocol dependent, we still have option keys as nodes ...
        #inputs = generate_scf_inputs(process_class, protocol, code, structure, override={'relax': {}})



        if relaxation_type == RelaxType.ATOMS:
            relaxation_mode = 'force'
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        if threshold_forces is not None:
            # Fleur expects atomic units i.e Hartree/bohr
            conversion_fac =  51.421
            force_criterion = threshold_forces / 51.421
        else:
            force_criterion = 0.001

        if threshold_stress is not None:
            pass #TODO

        wf_para = Dict(dict={
                      'relax_iter': 5,
                      'film_distance_relaxation': False,
                      'force_criterion': force_criterion,
                      'change_mixing_criterion': 0.025,
                      'atoms_off': []
                    })

        wf_para_scf = Dict(dict={'fleur_runmax': 2,
                    'itmax_per_run': 120,
                    'force_converged': force_criterion, # Check
                    'force_dict': {'qfix': 2,
                              'forcealpha': 0.75,
                              'forcemix': 'straight'},
                    'use_relax_xml': True,
                    'serial': False,
                    'mode': relaxation_mode,
                   })

        inputs = {'scf': {'wf_parameters': wf_para_scf,
                          'structure': structure,
                          #'calc_parameters': parameters,
                          #'options': options_scf,
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
