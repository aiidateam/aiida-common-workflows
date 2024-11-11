"""Implementation of `aiida_common_workflows.common.relax.generator.CommonRelaxInputGenerator` for FLEUR."""
import collections
import pathlib
import typing as t

import yaml
from aiida import engine, orm, plugins
from aiida.common.constants import elements

from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.generators import ChoiceType, CodeType

from ..generator import CommonRelaxInputGenerator

__all__ = ('FleurCommonRelaxInputGenerator',)

StructureData = plugins.DataFactory('core.structure')


class FleurCommonRelaxInputGenerator(CommonRelaxInputGenerator):
    """Generator of inputs for the `FleurCommonRelaxWorkChain`."""

    _default_protocol = 'moderate'
    _protocols: t.ClassVar = {
        'fast': {'description': 'return in a quick way a result that may not be reliable'},
        'moderate': {'description': 'reliable result (could be published), but no emphasis on convergence'},
        'precise': {'description': 'high level of accuracy'},
        'oxides_validation': {
            'description': 'high level of accuracy. Used for validating oxide results for common-workflows'
        },
        'verification-PBE-v1': {
            'description': 'high level of accuracy. Used for validating oxide results for common-workflows'
        },
    }

    def __init__(self, *args, **kwargs):
        """Construct an instance of the input generator, validating the class attributes."""
        self._initialize_protocols()
        super().__init__(*args, **kwargs)

    def _initialize_protocols(self):
        """Initialize the protocols class attribute by parsing them from the configuration file."""
        with open(str(pathlib.Path(__file__).parent / 'protocol.yml'), encoding='utf-8') as handle:
            self._protocols = yaml.safe_load(handle)

    @classmethod
    def define(cls, spec):
        """Define the specification of the input generator.

        The ports defined on the specification are the inputs that will be accepted by the ``get_builder`` method.
        """
        super().define(spec)
        spec.inputs['spin_type'].valid_type = ChoiceType((SpinType.NONE, SpinType.COLLINEAR))
        spec.inputs['relax_type'].valid_type = ChoiceType((RelaxType.NONE, RelaxType.POSITIONS))
        spec.inputs['electronic_type'].valid_type = ChoiceType((ElectronicType.METAL, ElectronicType.INSULATOR))
        spec.inputs['protocol'].valid_type = ChoiceType(
            ('fast', 'moderate', 'precise', 'oxides_validation', 'verification-PBE-v1')
        )
        spec.input('engines.inpgen.code', valid_type=orm.Code, serializer=orm.load_code)
        spec.input('engines.inpgen.options', non_db=True, valid_type=dict, required=False)
        spec.inputs['engines']['relax']['code'].valid_type = CodeType('fleur.fleur')
        spec.inputs['engines']['inpgen']['code'].valid_type = CodeType('fleur.inpgen')

    def _construct_builder(self, **kwargs) -> engine.ProcessBuilder:  # noqa: PLR0912,PLR0915
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

        inpgen_code = engines['inpgen']['code']
        fleur_code = engines['relax']['code']
        options = engines['relax'].get('options', {})
        options_scf = orm.Dict(dict=options)
        # Checks if protocol exists
        if protocol not in self.get_protocol_names():
            import warnings

            warnings.warn(f'no protocol implemented with name {protocol}, using default moderate')
            protocol = self.get_default_protocol_name()
        else:
            protocol = self.get_protocol(protocol)

        builder = self.process_class.get_builder()

        if threshold_forces is not None:
            # Fleur expects atomic units i.e Hartree/bohr
            conversion_fac = 51.421
            force_criterion = threshold_forces / conversion_fac
        else:
            force_criterion = 0.001

        if threshold_stress is not None:
            pass  # Stress is not supported

        molecule = False
        if structure.pbc == (False, False, False):
            molecule = True
            # we have to change the structure

            # check if vaccum box
            # maybe check if b-vectors are shorter than 10 A
            # else elongate them

            # make pbc (True, True, True)
            # keep provenance?
            structure = structure.clone()
            structure.pbc = (True, True, True)
        film_relax = not structure.pbc[-1]

        default_wf_para = {
            'relax_iter': 5,
            'film_distance_relaxation': film_relax,
            'force_criterion': force_criterion,
            'change_mixing_criterion': 0.025,
            'atoms_off': [],
            'run_final_scf': True,  # we always run a final scf after the relaxation
            'relaxation_type': 'atoms',
        }
        wf_para_dict = recursive_merge(default_wf_para, protocol.get('relax', {}))

        parameters = None

        # Relax type options
        if relax_type == RelaxType.POSITIONS:
            relaxation_mode = 'force'
        elif relax_type == RelaxType.NONE:
            relaxation_mode = 'force'
            wf_para_dict['relax_iter'] = 0
            wf_para_dict['relaxation_type'] = None
        else:
            raise ValueError(f'relaxation type `{relax_type.value}` is not supported')

        # We reduce the number of sigfigs for the cell and atom positions accounts for less
        # numerical inpgen errors during relaxation and accuracy is still enough for this purpose
        # We also currently assume that all common-workflow protocols exist in fleur
        settings = orm.Dict(
            dict={
                'significant_figures_cell': 9,
                'significant_figures_position': 9,
                'profile': protocol['inpgen-protocol'],
            }
        )

        wf_para = orm.Dict(dict=wf_para_dict)

        default_scf = {
            'fleur_runmax': 2,
            'itmax_per_run': 120,
            'force_converged': force_criterion,
            'force_dict': {'qfix': 2, 'forcealpha': 0.75, 'forcemix': 'straight'},
            'use_relax_xml': True,
            'mode': relaxation_mode,
        }
        protocol_scf_para = protocol.get('scf', {})
        kmax = protocol_scf_para.pop('k_max_cutoff', None)  # for now always None, later consider clean up

        if molecule:  # We want to use only one kpoint, can be overwritten by user input
            protocol_scf_para['kpoints_distance'] = 100000000
            # In addition we might want to use a different basis APW+LO?

        wf_para_scf_dict = recursive_merge(default_scf, protocol_scf_para)

        if reference_workchain is not None:
            parameters = get_parameters(reference_workchain)
            if 'kpt' in parameters.get_dict():
                wf_para_scf_dict.pop('kpoints_distance', None)
                if protocol_scf_para.get('kpoints_force_gamma', False):
                    parameters = parameters.get_dict()
                    parameters['kpt']['gamma'] = True
                    parameters = orm.Dict(dict=parameters)

        wf_para_scf = orm.Dict(dict=wf_para_scf_dict)

        # User specification overrides previous workchain!
        if 'calc_parameters' in kwargs:
            parameters = kwargs.pop('calc_parameters')

        parameters, structure = prepare_calc_parameters(parameters, spin_type, magnetization_per_site, structure, kmax)

        inputs = {
            'scf': {
                'wf_parameters': wf_para_scf,
                'structure': structure,
                'calc_parameters': parameters,
                'settings_inpgen': settings,
                'options': options_scf,
                # options do not matter on QM, in general they do...
                'inpgen': inpgen_code,
                'fleur': fleur_code,
            },
            'wf_parameters': wf_para,
        }

        builder._merge(inputs)

        return builder


def prepare_calc_parameters(parameters, spin_type, magnetization_per_site, structure, kmax):
    """Prepare a calc_parameter node for a inpgen jobcalc

    Depending on the imports merge information

    :param parameters: given calc_parameter orm.Dict node to merge with
    :param spin_type: type of magnetic calculation
    :param magnetization_per_site: list
    :param kmax: int, basis cutoff for the simulations
    :return: orm.Dict
    """

    # parameters_b = None

    # Spin type options
    if spin_type == SpinType.NONE:
        jspins = 1
    else:
        jspins = 2
    add_parameter_dict = {'comp': {'jspins': jspins}}

    # electronic Structure options
    # None. Gff we want to increase the smearing and kpoint density in case of metal

    if kmax is not None:  # add kmax from protocol
        add_parameter_dict = recursive_merge(add_parameter_dict, {'comp': {'kmax': kmax}})
    if parameters is not None:
        add_parameter_dict = recursive_merge(add_parameter_dict, parameters.get_dict())
        # In general better use aiida-fleur merge methods for calc parameters...

    if magnetization_per_site is not None:
        # Do for now sake we have this. If the structure is not rightly prepared it will run, but
        # the set magnetization will be wrong
        atomic_numbers = {data['symbol']: num for num, data in elements.items()}

        if spin_type == SpinType.NONE:
            import warnings

            warnings.warn('`magnetization_per_site` will be ignored as `spin_type` is set to SpinType.NONE')
        if spin_type == SpinType.COLLINEAR:
            # add atom lists for each kind and set bmu in muBohr
            # this will break symmetry and changes the structure, if needed
            # be careful here because this may override things the plugin is during already.
            # This is very fragile and not robust, it will be wrong if input structure is wrong,
            # i.e does not have enough kinds but we do not change the input structure that way.
            # In the end this should be implemented aiida-fleur and imported
            mag_dict = {}
            sites = list(structure.sites)
            for i, val in enumerate(magnetization_per_site):
                kind_name = sites[i].kind_name
                kind = structure.get_kind(kind_name)
                site_symbol = kind.symbols[0]  # assume atoms
                atomic_number = atomic_numbers[site_symbol]

                if kind_name != site_symbol:
                    head = kind_name.rstrip('0123456789')
                    try:
                        kind_namet = int(kind_name[len(head) :])
                    except ValueError:
                        kind_namet = 0
                    kind_id = f'{atomic_number}.{kind_namet}'
                else:
                    kind_id = f'{atomic_number}'
                mag_dict[f'atom{i}'] = {'z': atomic_number, 'id': kind_id, 'bmu': val}
            # Better would be a valid parameter data merge from aiida-fleur, to merge atom lists
            # right
            add_parameter_dict = recursive_merge(add_parameter_dict, mag_dict)
            # structure, parameters_b = break_symmetry(structure, parameterdata=orm.Dict(dict=add_parameter_dict))

    new_parameters = orm.Dict(dict=add_parameter_dict)

    return new_parameters, structure


def get_parameters(reference_workchain):
    """
    Extracts the FLAPW parameter for inpgen from a given previous workchain
    It finds the last Fleur Calcjob or Inpgen calc and extracts the
    parameters from its fleurinpdata node
    :param reference_workchain: Some workchain which contains at least one
                               Fleur CalcJob or Inpgen CalcJob.
    :return: Dict node of parameters ready to use, or None
    """
    from aiida.common.exceptions import NotExistent
    from aiida.plugins import WorkflowFactory
    from aiida_fleur.tools.common_fleur_wf import find_last_submitted_workchain

    fleur_scf_wc = WorkflowFactory('fleur.scf')
    # Find Fleurinp
    try:
        last_base_relax = find_last_submitted_workchain(reference_workchain)
        last_relax = find_last_submitted_workchain(orm.load_node(last_base_relax))
        last_scf = find_last_submitted_workchain(orm.load_node(last_relax))
        last_scf = orm.load_node(last_scf)
    except NotExistent:
        # something went wrong in the previous workchain run
        # .. we just continue without previous parameters but defaults.
        return None
    if last_scf.process_class is fleur_scf_wc:
        fleurinp = last_scf.outputs.fleurinp
    else:
        return None
    # Be aware that this parameter node is incomplete. LOs and econfig is
    # currently missing for example, also we do not reuse the same kpoints.
    # the density is likely the same, but the set may vary.
    parameters = fleurinp.get_parameterdata_ncf(write_ids=False)  # This is not a calcfunction!

    return parameters


# Same code as in Quantum_espresso generator.py could be moved somewhere else and imported
def recursive_merge(left: t.Dict[str, t.Any], right: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Recursively merge two dictionaries into a single dictionary.

    :param left: first dictionary.
    :param right: second dictionary.
    :return: the recursively merged dictionary.
    """
    for key, value in left.items():
        if key in right:
            if isinstance(value, collections.abc.Mapping) and isinstance(right[key], collections.abc.Mapping):
                right[key] = recursive_merge(value, right[key])

    merged = left.copy()
    merged.update(right)

    return merged
