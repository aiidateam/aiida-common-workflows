# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for ABINIT."""
import collections
import pathlib
from typing import Any, Dict
import yaml

from aiida import engine
from aiida import orm 
from aiida import plugins
from aiida.common import exceptions

from ..generator import RelaxInputsGenerator, RelaxType
from qe_tools import CONSTANTS

__all__ = ('AbinitRelaxInputsGenerator',)

StructureData = plugins.DataFactory('structure')

class AbinitRelaxInputsGenerator(RelaxInputsGenerator):
    """Input generator for the `AbinitRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _calc_types = {'relax': {'code_plugin': 'abinit', 'description': 'The code to perform the relaxation.'}}
    _relax_types = {
        RelaxType.ATOMS: 'Relax only the atomic positions while keeping the cell fixed.',
        RelaxType.ATOMS_CELL: 'Relax both atomic positions and the cell.'
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
        protocol,
        relaxation_type: RelaxType,
        threshold_forces: float = None,
        threshold_stress: float = None,
        previous_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """Return a process builder for the corresponding workchain class with inputs set according to the protocol.

        :param structure: the structure to be relaxed
        :param calc_engines: ...
        :param protocol: the protocol to use when determining the workchain inputs
        :param relaxation_type: the type of relaxation to perform, instance of `RelaxType`
        :param threshold_forces: target threshold for the forces in eV/Å.
        :param threshold_stress: target threshold for the stress in eV/Å^3.
        :return: a `aiida.engine.processes.ProcessBuilder` instance ready to be submitted.
        """
        # pylint: disable=too-many-locals

        super().get_builder(
            structure, calc_engines, protocol, relaxation_type, threshold_forces, threshold_stress, previous_workchain,
            **kwargs
        )

        # The builder.
        builder = self.process_class.get_builder()        

        # Input structure.
        builder.abinit.structure = structure

        # Input parameters.
        parameters = self.get_protocol(protocol)['base']['parameters']
        
        if relaxation_type == RelaxType.ATOMS:
            optcell = 0
            ionmov = 22
        elif relaxation_type == RelaxType.ATOMS_CELL:
            optcell = 2
            ionmov = 22
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        parameters['optcell'] = optcell
        parameters['ionmov'] = ionmov
        parameters['ecutsm'] = 0.5

        if threshold_forces is not None:
            # Here threshold_forces is provided in eV/Å
            threshold = threshold_forces * CONSTANTS.bohr_to_ang / (CONSTANTS.ry_to_ev * 2.0)
            # The tolmxf parameter in Abinit should be provided in Ha/Bohr
            # The tolmxf sets a maximal absolute force tolerance below which BFGS structural 
            # relaxation iterations will stop. 
            parameters['tolmxf'] = threshold 

        if (threshold_stress is not None and threshold_forces is not None):
            thr_stress = threshold_stress * CONSTANTS.bohr_to_ang**3 / (CONSTANTS.ry_to_ev * 2.0)
            thr_force = threshold_forces * CONSTANTS.bohr_to_ang / (CONSTANTS.ry_to_ev * 2.0)
            thr_fact = thr_force / thr_stress
            parameters['tolmxf'] = thr_force
            parameters['strfact'] = thr_fact

        # Additional files to be retrieved.
        builder.abinit.settings = orm.Dict(dict={'additional_retrieve_list': ['aiidao_HIST.nc']})


        #merged = recursive_merge(protocol, override)  
        builder.abinit.parameters = orm.Dict(dict=parameters)

        # Abinit code.
        #builder.abinit.code = orm.load_code(calc_engines['relax']['code'])
        CODE = 'abinit-9.2.1-ab@localhost'
        code = orm.Code.get_from_string(CODE)
        builder.abinit.code = code 

        # Run options.
        builder.abinit.metadata.options = calc_engines['relax']['options']

        return builder


#def recursive_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
#    """Recursively merge two dictionaries into a single dictionary.
#
#    :param left: first dictionary.
#    :param right: second dictionary.
#    :return: the recursively merged dictionary.
#    """
#    for key, value in left.items():
#        if key in right:
#            if isinstance(value, collections.Mapping) and isinstance(right[key], collections.Mapping):
#                right[key] = recursive_merge(value, right[key])
#
#    merged = left.copy()
#    merged.update(right)
#
#    return merged

