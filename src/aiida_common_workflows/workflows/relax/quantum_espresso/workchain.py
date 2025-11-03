"""Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""
import pint
from aiida import orm
from aiida.engine import calcfunction
from aiida.plugins import WorkflowFactory

from ..workchain import CommonRelaxWorkChain
from .generator import QuantumEspressoCommonRelaxInputGenerator

__all__ = ('QuantumEspressoCommonRelaxWorkChain',)

OPTIONAL_OUTPUT_PORTS = ['total_magnetization', 'fermi_energy', 'fermi_energy_up', 'fermi_energy_down']


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

    results = {'total_energy': orm.Float(total_energy)}

    for output_name in OPTIONAL_OUTPUT_PORTS:
        if output_name in parameters.base.attributes:
            results[output_name] = orm.Float(parameters.base.attributes.get(output_name))

    return results


class QuantumEspressoCommonRelaxWorkChain(CommonRelaxWorkChain):
    """Implementation of `aiida_common_workflows.common.relax.workchain.CommonRelaxWorkChain` for Quantum ESPRESSO."""

    _process_class = WorkflowFactory('quantumespresso.pw.relax')
    _generator_class = QuantumEspressoCommonRelaxInputGenerator

    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
        outputs = self.ctx.workchain.outputs

        results = extract_from_parameters(outputs.output_parameters)
        forces, stress = extract_from_trajectory(outputs.output_trajectory).values()

        total_energy = results.get('total_energy')

        if 'output_structure' in outputs:
            self.out('relaxed_structure', outputs.output_structure)

        self.out('total_energy', total_energy)
        self.out('forces', forces)
        self.out('stress', stress)

        for output_name in OPTIONAL_OUTPUT_PORTS:
            if output_name in results:
                self.out(output_name, results[output_name])
