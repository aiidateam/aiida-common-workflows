# -*- coding: utf-8 -*-
"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""
from aiida import orm
from aiida.common.exceptions import NotExistentAttributeError
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import VaspCommonRelaxInputGenerator

__all__ = ('VaspCommonRelaxWorkChain',)


@calcfunction
def get_stress(stress):
    """Return the final stress array."""
    stress_data = orm.ArrayData()
    stress_data.set_array(name='stress', array=stress.get_array('final'))

    return stress_data


@calcfunction
def get_forces(forces):
    """Return the final forces array.."""
    forces_data = orm.ArrayData()
    forces_data.set_array(name='forces', array=forces.get_array('final'))

    return forces_data


@calcfunction
def get_total_extrapolated_energy(energies):
    """Return the total extrapolated energy from the energies array."""
    # We extract by default the energies of the last electronic step, unless special flags are set.
    total_extrapolated_energy = energies.get_array('energy_extrapolated')[0]
    total_energy = orm.Float(total_extrapolated_energy)

    return total_energy


@calcfunction
def get_total_cell_magnetic_moment(misc):
    """Return the total cell magnetic moment."""
    magnetization = misc.get_dict()['magnetization']
    if not magnetization:
        # If list is empty, we have no magnetization
        magnetization = 0.0
    else:
        # Assume we do not run non-collinear
        magnetization = magnetization[0]

    return orm.Float(magnetization)


class VaspCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for VASP."""

    _process_class = WorkflowFactory('vasp.relax')
    _generator_class = VaspCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        try:
            self.out('relaxed_structure', self.ctx.workchain.outputs.relax__structure)
        except NotExistentAttributeError:
            # We have no control of when we want to perform relaxations here,
            # this is up to the calling workchains, so do not set the relaxed structure if a
            # relaxation was not requested.
            pass
        self.out('total_magnetization', get_total_cell_magnetic_moment(self.ctx.workchain.outputs.misc))
        self.out('total_energy', get_total_extrapolated_energy(self.ctx.workchain.outputs.energies))
        self.out('forces', get_forces(self.ctx.workchain.outputs.forces))
        self.out('stress', get_stress(self.ctx.workchain.outputs.stress))
