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
from aiida_common_workflows.generators import ChoiceType, CodeType
from ..generator import CommonRelaxInputGenerator

__all__ = ('Wien2kCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('structure')


class Wien2kCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Generator of inputs for the Wien2kCommonRelaxWorkChain"""

    _default_protocol = 'moderate'

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

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE,))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE,))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('wien2k-run123_lapw')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)
        electronic_type = kwargs['electronic_type']

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
                '-fermits': self._protocols[protocol]['parameters']['fermi-temp-Ry'],
                '-nokshift': self._protocols[protocol]['parameters']['nokshift'],
                '-noprec': self._protocols[protocol]['parameters']['noprec'],
                '-numk': self._protocols[protocol]['parameters']['numk'],
                '-numk2': self._protocols[protocol]['parameters']['numk2'],
                }) # run123_lapw [param]
        if electronic_type == ElectronicType.INSULATOR:
            inpdict['-nometal'] = True
        if reference_workchain: # ref. workchain is passed as input
            # derive Rmt's from the ref. workchain and pass as input
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
            inpdict['-red'] = red_string # pass Rmt's as input to subsequent wrk. chains
            # derive k mesh from the ref. workchain and pass as input
            if 'kmesh3' in ref_wrkchn_res_dict: # check if kmesh3 is in results dict
                if ref_wrkchn_res_dict['kmesh3']: # check if the k mesh is not empty
                    inpdict['-numk'] = '0' + ' ' + ref_wrkchn_res_dict['kmesh3']
            if 'kmesh3k' in ref_wrkchn_res_dict: # check if kmesh3k is in results dict
                if ref_wrkchn_res_dict['kmesh3k']: # check if the k mesh is not empty
                    inpdict['-numk2'] = '0' + ' ' + ref_wrkchn_res_dict['kmesh3k']
            if 'fftmesh3k' in ref_wrkchn_res_dict: # check if fftmesh3k is in results dict
                if ref_wrkchn_res_dict['fftmesh3k']: # check if the FFT mesh is not empty
                    inpdict['-fft'] = ref_wrkchn_res_dict['fftmesh3k']

        res = NodeNumberJobResource(num_machines=1, num_mpiprocs_per_machine=1, num_cores_per_mpiproc=1) # set resources
        if 'options' in engines['relax']:
            print("WIEN2k+AiiDA does not support more than 1 core per job")
        builder = self.process_class.get_builder()
        builder.aiida_structure = structure
        builder.code = engines['relax']['code'] # load wien2k-run123_lapw code
        builder.inpdict = inpdict

        return builder
