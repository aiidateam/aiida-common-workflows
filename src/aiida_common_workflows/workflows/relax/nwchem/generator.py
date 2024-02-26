"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for NWChem."""
import pathlib
import warnings

import numpy as np
import yaml
from aiida import engine, orm, plugins

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('NwchemCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')

HA_BOHR_TO_EV_A = 51.42208619083232


class NwchemCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Input generator for the `NwchemCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(pathlib.Path(__file__).parent / 'protocol.yml', encoding='utf-8') as handle:
            self._protocols = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType(
            (RelaxType.NONE, RelaxType.CELL, RelaxType.POSITIONS, RelaxType.POSITIONS_CELL)
        )
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('nwchem.nwchem')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
        """Construct a process builder based on the provided keyword arguments.

        The keyword arguments will have been validated against the input generator specification.
        """

        structure = kwargs['structure']
        engines = kwargs['engines']
        protocol = kwargs['protocol']
        spin_type = kwargs['spin_type']
        relax_type = kwargs['relax_type']
        electronic_type = kwargs['electronic_type']
        magnetization_per_site = kwargs.get('magnetization_per_site', None)
        threshold_forces = kwargs.get('threshold_forces', None)
        threshold_stress = kwargs.get('threshold_stress', None)
        reference_workchain = kwargs.get('reference_workchain', None)

        # Protocol
        parameters = self.get_protocol(protocol)
        parameters.pop('description', None)
        parameters.pop('name', None)

        # # kpoints
        target_spacing = parameters.pop('kpoint_spacing')
        if reference_workchain:
            ref_kpoints = reference_workchain.inputs.nwchem__parameters['nwpw']['monkhorst-pack']
            parameters['nwpw']['monkhorst-pack'] = ref_kpoints
        else:
            reciprocal_axes_lengths = np.linalg.norm(np.linalg.inv(structure.cell), axis=1)
            kpoints = np.ceil(reciprocal_axes_lengths / target_spacing).astype(int).tolist()
            parameters['nwpw']['monkhorst-pack'] = '{} {} {}'.format(*kpoints)

        # Relaxation type
        if relax_type == RelaxType.POSITIONS:
            parameters['task'] = 'band optimize'
        elif relax_type == RelaxType.POSITIONS_CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.'}
        elif relax_type == RelaxType.CELL:
            parameters['task'] = 'band optimize'
            parameters['set'] = {'includestress': '.true.', 'nwpw:zero_forces': '.true.'}
        elif relax_type == RelaxType.NONE:
            parameters['task'] = 'band gradient'
            parameters.pop('driver', None)
        else:
            raise ValueError(f'relax_type `{relax_type.value}` is not supported')

        # Electronic type
        if electronic_type == ElectronicType.INSULATOR:
            pass
        elif electronic_type == ElectronicType.METAL:
            parameters['nwpw']['smear'] = 'fermi'
            parameters['nwpw']['scf'] = 'Anderson outer_iterations 0 Kerker 2.0'
            parameters['nwpw']['loop'] = '10 10'
            parameters['nwpw'].pop('lmbfgs', None)  # Revert to CG
        else:
            raise ValueError(f'electronic_type `{electronic_type.value}` is not supported')

        # Spin type
        if spin_type == SpinType.NONE:
            pass
        elif spin_type == SpinType.COLLINEAR:
            parameters['nwpw']['odft'] = ''
        else:
            raise ValueError(f'spin_type `{spin_type.value}` is not supported')

        # Magnetization per site
        # Not implemented yet - one has to specify the site, spin AND angular momentum
        if magnetization_per_site:
            raise ValueError('magnetization per site not yet supported')

        # Add a unit cell to the geometry stanza
        add_cell = orm.Bool(True)

        # Special case of a molecule in "open boundary conditions"
        if structure.pbc == (False, False, False):
            warnings.warn('PBCs set to false in input structure: assuming this is a molecular calculation')
            add_cell = orm.Bool(False)
            # We don't use the geometry stanza for the cell, but add it in the parameters
            parameters['nwpw']['simulation_cell angstroms'] = {
                'lattice': {
                    'lat_a': structure.cell_lengths[0],
                    'lat_b': structure.cell_lengths[1],
                    'lat_c': structure.cell_lengths[2],
                    'alpha': structure.cell_angles[0],
                    'beta': structure.cell_angles[1],
                    'gamma': structure.cell_angles[2],
                }
            }
            parameters['driver']['redoautoz'] = ''  # To ensure internal coordinates are refreshed
            parameters['nwpw']['cutoff'] = 140
            parameters['task'] = 'pspw optimize'

            parameters['nwpw'].pop('monkhorst-pack', None)
            parameters['nwpw'].pop('ewald_rcut', None)
            parameters['nwpw'].pop('ewald_ncut', None)
            parameters['nwpw'].pop('smear', None)
            parameters['nwpw'].pop('scf', None)
            parameters['nwpw'].pop('loop', None)

        # Forces threshold.
        if threshold_forces is not None:
            parameters['driver']['xmax'] = f'{threshold_forces / HA_BOHR_TO_EV_A}'

        # Stress threshold.
        if threshold_stress is not None:
            raise ValueError('Overall stress is not used as a stopping criterion in NWChem')

        # Prepare builder
        builder = self.process_class.get_builder()
        builder.nwchem.code = engines['relax']['code']
        builder.nwchem.metadata.options = engines['relax']['options']
        builder.nwchem.structure = structure
        builder.nwchem.add_cell = add_cell
        builder.nwchem.parameters = orm.Dict(dict=parameters)

        return builder
