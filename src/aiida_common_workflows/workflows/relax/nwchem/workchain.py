"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for NWChem."""
import numpy as np
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import NwchemCommonRelaxInputGenerator

__all__ = ('NwchemCommonRelaxWorkChain',)

NwchemBaseWorkChain = WorkflowFactory('nwchem.base')

HA_BOHR_TO_EV_A = 51.42208619083232
HA_TO_EV = 27.211396


@calcfunction
def get_total_energy(parameters):
    """Return the total energy [eV] from the output parameters node for an energy calculation."""
    return orm.Float(parameters['total_energy'] * HA_TO_EV)


@calcfunction
def get_final_energy(parameters):
    """Return the total energy [eV] from the output parameters node for an optimisation calculation."""
    return orm.Float(parameters['final_energy']['total_energy'] * HA_TO_EV)


@calcfunction
def get_forces(parameters):
    """Return the forces array [eV/ang] from the output parameters node."""
    forces_au = np.array(parameters['final_energy']['forces'], dtype=float)
    forces_ev = orm.ArrayData()
    forces_ev.set_array(name='forces', array=forces_au * HA_BOHR_TO_EV_A)
    return forces_ev


class NwchemCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for NWChem."""

    _process_class = NwchemBaseWorkChain
    _generator_class = NwchemCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        if 'output_structure' in self.ctx.workchain.outputs:
            self.out('relaxed_structure', self.ctx.workchain.outputs.output_structure)
            self.out('total_energy', get_final_energy(self.ctx.workchain.outputs.output_parameters))
        else:
            self.out('total_energy', get_total_energy(self.ctx.workchain.outputs.output_parameters))

        self.out('forces', get_forces(self.ctx.workchain.outputs.output_parameters))
