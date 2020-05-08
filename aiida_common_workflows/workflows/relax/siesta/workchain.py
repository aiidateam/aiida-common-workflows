from aiida.orm import (Float, Str, ArrayData, Dict, StructureData)
from aiida.engine import calcfunction
from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida_common_workflows.workflows.relax.workchain import CommonRelaxWorkChain

@calcfunction
def get_energy(pardict):
    return Float(pardict['E_KS'])

@calcfunction
def get_forces_and_stress(totalarray):
    forces = ArrayData()
    forces.set_array(name='forces', array=totalarray.get_array('forces'))
    stress = ArrayData()
    stress.set_array(name='stress', array=totalarray.get_array('stress'))
    return {'forces': forces, 'stress': stress}


class SiestaRelaxWorkChain(CommonRelaxWorkChain):
    """
    Workchain to relax a structure through Siesta. The outputs
    follows some standardization agreed at AiiDA Hackaton of Feb 2020.
    """
    _process_class = SiestaBaseWorkChain

    def convert_outputs(self):
        self.report('Relaxation task concluded sucessfully, converting outputs')
        self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
        self.out('total_energy', get_energy(self.ctx.workchain.outputs.output_parameters))
        res_dict = get_forces_and_stress(self.ctx.workchain.outputs.forces_and_stress)
        self.out('forces', res_dict['forces'])
        self.out('stress', res_dict['stress'])

