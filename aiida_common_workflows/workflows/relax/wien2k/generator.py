# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for Wien2k."""
import os
from typing import Any, Dict, List, Tuple, Union

import yaml

from aiida import engine
from aiida import orm
from aiida import plugins
from aiida.common import exceptions
from aiida.schedulers.datastructures import NodeNumberJobResource

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from ..generator import CommonRelaxInputGenerator

__all__ = ('Wien2kCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')


class Wien2kCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Generator of inputs for the Wien2kCommonRelaxWorkChain"""

    _default_protocol = 'moderate'

    _engine_types = {
        'relax': {
            'code_plugin': 'wien2k-run123_lapw',
            'description': 'The code runs SCF for WIEN2k.'
        }
    }
    _relax_types = {
        RelaxType.NONE: 'no relaxation performed'#,
        # RelaxType.POSITIONS: 'latice shape and volume fixed, only atomic positions are relaxed',
        # RelaxType.POSITIONS_CELL: 'lattice relaxed together with atomic coordinates. Allows '
        # 'to target hydro-static pressures or arbitrary stress tensors.',
        # RelaxType.POSITIONS_SHAPE: 'relaxation at constant volume.'
    }
    _spin_types = {
        SpinType.NONE: 'non magnetic calculation'#,
        # SpinType.COLLINEAR: 'magnetic calculation with collinear spins'
    }
    _electronic_types = {
        ElectronicType.METAL: 'For Wien2k, metals require a larger k mesh',
        ElectronicType.INSULATOR: 'For Wien2k, insulators require a smaller k mesh'
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""

        self._initialize_protocols()

        super().__init__(*args, **kwargs)

        def raise_invalid(message):
            raise RuntimeError('invalid protocol registry `{}`: '.format(self.__class__.__name__) + message)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        _filepath = os.path.join(os.path.dirname(__file__), 'protocol.yml')

        with open(_filepath) as _thefile:
            self._protocols = yaml.full_load(_thefile)

    def get_builder(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
        self,
        structure: StructureData,
        engines: Dict[str, Any],
        *,
        protocol: str = None,
        relax_type: Union[RelaxType, str] = RelaxType.NONE,
        electronic_type: Union[ElectronicType, str] = ElectronicType.METAL,
        spin_type: Union[SpinType, str] = SpinType.NONE,
        magnetization_per_site: Union[List[float], Tuple[float]] = None,
        threshold_forces: float = None,
        threshold_stress: float = None,
        reference_workchain=None,
        **kwargs
    ) -> engine.ProcessBuilder:
        """
        Return a process builder for the corresponding workchain class with inputs set according to the protocol.

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
        if protocol not in self.get_protocol_names():
            import warnings
            warnings.warn('no protocol implemented with name {}, using default moderate'.format(protocol))
            protocol = self.get_default_protocol_name()
        if not all(x in engines.keys() for x in ['relax']):
            raise ValueError('The `engines` dictionary must contain "relax" as outermost key')

        # construct input for run123_lapw
        inpdict = orm.Dict(dict={
                '-red': self._protocols[protocol]['parameters']['red'],
                '-i': self._protocols[protocol]['parameters']['max-scf-iterations'],
                '-ec': self._protocols[protocol]['parameters']['scf-ene-tol-Ry'],
                '-cc': self._protocols[protocol]['parameters']['scf-charge-tol'],
                '-fermit': self._protocols[protocol]['parameters']['fermi-temp-Ry'],
                '-deltak': self._protocols[protocol]['parameters']['deltak'],
                '-nokshift': self._protocols[protocol]['parameters']['nokshift']
                }) # run123_lapw [param]
        if electronic_type == ElectronicType.INSULATOR:
            inpdict['-nometal'] = True
        if reference_workchain: # ref. workchain is passed as input
            # derive Rmt's from the ref. workchain
            w2k_wchain = reference_workchain.get_outgoing(node_class=orm.WorkChainNode).one().node
            ref_wrkchn_res_dict = w2k_wchain.outputs.workchain_result.get_dict()
            rmt = ref_wrkchn_res_dict['Rmt']
            atm_lbl = ref_wrkchn_res_dict['atom_labels']
            if len(rmt) != len(atm_lbl):
                raise # the list with Rmt radii should match the list of elements
            red_string = ''
            for i in range(len(rmt)):
                red_string += atm_lbl[i] + ':' + str(rmt[i])
                if i < len(rmt)-1: # for all, but the last element of the list
                    red_string += ',' # append comma
            inpdict['-red'] = red_string # pass Rmt's as input

        res = NodeNumberJobResource(num_machines=1, num_mpiprocs_per_machine=1, num_cores_per_mpiproc=1) # set resources
        if 'options' in engines['relax']:
            print("WIEN2k+AiiDA does not support more than 1 core per job")
        builder = self.process_class.get_builder()
        builder.aiida_structure = structure
        builder.code = orm.load_code(engines['relax']['code'])
        builder.inpdict = inpdict

        return builder
