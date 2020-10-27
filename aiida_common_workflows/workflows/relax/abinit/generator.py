# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.RelaxInputGenerator` for ABINIT."""
import collections
import pathlib
from typing import Any, Dict

import yaml
from pymatgen.core import units

from aiida import engine, orm, plugins
from aiida.common import exceptions
from aiida_common_workflows.workflows.relax.generator import (RelaxInputsGenerator, RelaxType)

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

        protocol = self.get_protocol(protocol)
        code = calc_engines['relax']['code']
        override = {'abinit': {'metadata': {'options': calc_engines['relax']['options']}}}
        # the type of magnetisation to be used
        magnetism = calc_engines['magnetism']
        # value for the initial magnetisation along the z axis.
        initial_mag = float(calc_engines['initial_mag'])
        # whether or not to use spin-orbit coupling
        soc = calc_engines['SOC']
        # whether or not the material is a metal
        metal = calc_engines['metal']

        builder = self.process_class.get_builder()
        inputs = generate_inputs(self.process_class._process_class, protocol, code, structure, override)  # pylint: disable=protected-access
        builder._update(inputs)  # pylint: disable=protected-access
        #print('inputs ',inputs)
        #print('nbnd ',inputs['abinit']['parameters']['nbnd'])

        if relaxation_type == RelaxType.ATOMS:
            optcell = 0
            ionmov = 22
        elif relaxation_type == RelaxType.ATOMS_CELL:
            optcell = 2
            ionmov = 22
        else:
            raise ValueError('relaxation type `{}` is not supported'.format(relaxation_type.value))

        builder.abinit['parameters']['optcell'] = optcell
        builder.abinit['parameters']['ionmov'] = ionmov

        # Add the information linked with magnetism and SOC 
        if magnetism == 'ferro':
            builder.abinit['parameters']['nsppol'] = 2
            builder.abinit['parameters']['spinat'] = '0.0  0.0  '+str(initial_mag)
        if magnetism == 'anti':
            builder.abinit['parameters']['nsppol'] = 1
            builder.abinit['parameters']['nspden'] = 2
            builder.abinit['parameters']['spinat'] = '0.0  0.0  ' + str(initial_mag) + '\n     0.0  0.0  '+ str( - initial_mag)
        if metal == 'yes':
            # Fermi-Dirac smearing occupation with value defined by tsmear 
            builder.abinit['parameters']['occopt'] = 3
            builder.abinit['parameters']['tsmear'] = 0.01 # Ha
            # In the case of metals, one typically need a bit more bands. 
            # This adds 1.5 bands [rounded up] (times the number of atoms)
            builder.abinit['parameters']['fband'] =  1.5
        if soc == 'yes':
            builder.abinit['parameters']['nspinor'] = 2

        if threshold_forces is not None:
            # The Abinit threshold_forces is in Ha/Bohr
            threshold_f = threshold_forces * units.Ha_to_eV / units.bohr_to_ang  # eV/Å
            builder.abinit['parameters']['tolmxf'] = threshold_f
            if threshold_stress is not None:
                threshold_s = threshold_stress * units.Ha_to_eV / units.bohr_to_ang**3  # eV/Å^3
                strfact = threshold_f / threshold_s
                builder.abinit['parameters']['strfact'] = strfact
        else:
            threshold_f = 5.0e-5  # ABINIT default value
            if threshold_stress is not None:
                threshold_s = threshold_stress * units.Ha_to_eV / units.bohr_to_ang**3
                strfact = threshold_f / threshold_s
                builder.abinit['parameters']['strfact'] = strfact
                # How can we warn the user that we are using the tolxmf Abinit default value?
                builder.abinit['parameters']['tolmxf'] = threshold_f

        return builder


def generate_inputs(
    process_class: engine.Process,
    protocol: Dict,
    code: orm.Code,
    structure: StructureData,
    override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the input parameters for the given workchain type for a given code and structure.

    The override argument can be used to pass a dictionary with values for specific inputs that should override the
    defaults. This dictionary should have the same nested structure as the final input dictionary would have for the
    workchain submission.

    :param process_class: process class, either calculation or workchain,
        i.e. ``AbinitCalculation`` or ``AbinitBaseWorkChain``
    :param protocol: the protocol based on which to choose input parameters
    :param code: the code or code name to use
    :param magnetism: the type of magnetisation to be used 
    :param initial_mag: value for the initial magnetisation along the z axis.  
    :param soc: whether or not to use spin-orbit coupling
    :param structure: the structure
    :param override: a dictionary to override specific inputs
    :return: input dictionary
    """
    # pylint: disable=too-many-arguments,unused-argument
    from aiida.common.lang import type_check

    AbinitCalculation = plugins.CalculationFactory('abinit')  # pylint: disable=invalid-name
    AbinitBaseWorkChain = plugins.WorkflowFactory('abinit.base')  # pylint: disable=invalid-name

    type_check(structure, orm.StructureData)

    if not isinstance(code, orm.Code):
        try:
            code = orm.load_code(code)
        except (exceptions.MultipleObjectsError, exceptions.NotExistent) as exception:
            raise ValueError('could not load the code {}: {}'.format(code, exception))

    if process_class == AbinitCalculation:
        protocol = protocol['abinit']
        dictionary = generate_inputs_calculation(protocol, code, structure, override)
    elif process_class == AbinitBaseWorkChain:
        protocol = protocol['base']
        dictionary = generate_inputs_base(protocol, code, structure, override)
    else:
        raise NotImplementedError('process class {} is not supported'.format(process_class))

    return dictionary


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


def generate_inputs_base(protocol: Dict,
                         code: orm.Code,
                         structure: StructureData,
                         override: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate the inputs for the `AbinitBaseWorkChain` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    protocol['abinit'] = generate_inputs_calculation(protocol['abinit'], code, structure, override.get('abinit', {}))
    merged = recursive_merge(protocol, override or {})
    merged['pseudo_family'] = orm.Str(merged['pseudo_family'])

    return merged


def generate_inputs_calculation(
    protocol: Dict, code: orm.Code, structure: StructureData, override: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate the inputs for the `AbinitCalculation` for a given code, structure and pseudo potential family.

    :param protocol: the dictionary with protocol inputs.
    :param code: the code to use.
    :param structure: the input structure.
    :param override: a dictionary to override specific inputs.
    :return: the fully defined input dictionary.
    """
    merged = recursive_merge(protocol, override or {})

    dictionary = {
        'code': code,
        'structure': structure,
        'parameters': orm.Dict(dict=merged['parameters']),
        'metadata': merged.get('metadata', {})
    }

    return dictionary
