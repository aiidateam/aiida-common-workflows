"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""
import pint
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import QuantumEspressoCommonRelaxInputGenerator

__all__ = ('QuantumEspressoCommonRelaxWorkChain',)


@calcfunction
def extract_from_trajectory(trajectory):
    """Return the forces and stress arrays from the given trajectory data."""
    ureg = pint.UnitRegistry()

    forces = orm.ArrayData()
    forces.set_array(name='forces', array=trajectory.get_array('forces')[-1])

    stress_gpa = trajectory.get_array('stress')[-1] * ureg.GPa

    stress = orm.ArrayData()
    stress.set_array(name='stress', array=stress_gpa.to(ureg.electron_volt / ureg.angstrom**3).magnitude)

    return {'forces': forces, 'stress': stress}


@calcfunction
def extract_from_parameters(parameters):
    """Return the total energy and optionally the total magnetization from the given parameters node."""
    total_energy = parameters.base.attributes.get('energy')
    total_magnetization = parameters.base.attributes.get('total_magnetization', None)

    results = {'total_energy': orm.Float(total_energy)}

    if total_magnetization is not None:
        results['total_magnetization'] = orm.Float(total_magnetization)

    return results


class QuantumEspressoCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""

    _process_class = WorkflowFactory('quantumespresso.pw.relax')
    _generator_class = QuantumEspressoCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        result = extract_from_parameters(outputs.output_parameters).values()
        forces, stress = extract_from_trajectory(outputs.output_trajectory).values()

        try:
            total_energy, total_magnetization = result
        except ValueError:
            total_energy, total_magnetization = next(iter(result)), None

        if 'output_structure' in outputs:
            self.out('relaxed_structure', outputs.output_structure)

        if total_magnetization is not None:
            self.out('total_magnetization', total_magnetization)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
        self.out('stress', stress)
