"""Module with base wrapper workchain for common structure relaxation workchains."""
from abc import ABCMeta, abstractmethod

from aiida.engine import ToContext, WorkChain
from aiida.orm import ArrayData, Float, RemoteData, StructureData, TrajectoryData

from .generator import CommonRelaxInputGenerator

__all__ = ('CommonRelaxWorkChain',)


class CommonRelaxWorkChain(WorkChain, metaclass=ABCMeta):
    """Base workchain implementation that serves as a wrapper for common structure relaxation workchains.

    Subclasses should simply define the concrete plugin-specific relaxation workchain for the `_process_class` attribute
    and implement the `convert_outputs` class method to map the plugin specific outputs to the output spec of this
    common wrapper workchain.
    """

    _process_class = None
    _generator_class = None

    @classmethod
    def get_input_generator(cls) -> CommonRelaxInputGenerator:
        """Return an instance of the input generator for this work chain.

        :return: input generator
        """
        return cls._generator_class(process_class=cls)

    @classmethod
    def define(cls, spec):
        # yapf: disable
        super().define(spec)
        spec.expose_inputs(cls._process_class)
        spec.outline(
            cls.run_workchain,
            cls.inspect_workchain,
            cls.convert_outputs,
        )
        spec.output('relaxed_structure', valid_type=StructureData, required=False,
            help='All cell dimensions and atomic positions are in Ångstrom.')
        spec.output('forces', valid_type=ArrayData, required=False,
            help='The final forces on all atoms in eV/Å.')
        spec.output('stress', valid_type=ArrayData, required=False,
            help='The final stress tensor in eV/Å^3.')
        spec.output('trajectory', valid_type=TrajectoryData, required=False,
            help='All cell dimensions and atomic positions are in Ångstrom.')
        spec.output('total_energy', valid_type=Float, required=False,
            help='Total energy in eV.')
        spec.output('total_magnetization', valid_type=Float, required=False,
            help='Total magnetization in Bohr magnetons.')
        spec.output('remote_folder', valid_type=RemoteData, required=False,
            help='Folder of the last run calculation.')
        spec.exit_code(400, 'ERROR_SUB_PROCESS_FAILED',
            message='The `{cls}` workchain failed with exit status {exit_status}.')

    def run_workchain(self):
        """Run the wrapped workchain."""
        inputs = self.exposed_inputs(self._process_class)
        return ToContext(workchain=self.submit(self._process_class, **inputs))

    def inspect_workchain(self):
        """Inspect the terminated workchain."""
        cls = self._process_class.__name__
        if not self.ctx.workchain.is_finished_ok:
            exit_status = self.ctx.workchain.exit_status
            self.report(f'{cls}<{self.ctx.workchain.pk}> failed with exit status {exit_status}.')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(cls=cls, exit_status=exit_status)

        self.report(f'{cls}<{self.ctx.workchain.pk}> finished successfully.')

    @abstractmethod
    def convert_outputs(self):
        """Convert the outputs of the sub workchain to the common output specification."""
