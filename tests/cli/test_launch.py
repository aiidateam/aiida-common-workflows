"""Tests for the :mod:`aiida_common_workflows.cli.launch` module."""
import re

import click
import pytest
from aiida_common_workflows.cli import launch, utils


@pytest.mark.usefixtures('aiida_profile')
def test_relax(run_cli_command, generate_structure, generate_code):
    """Test the `launch relax` command."""
    structure = generate_structure().store()
    generate_code('gaussian').store()

    options = ['-S', str(structure.pk), '-d', 'gaussian']
    result = run_cli_command(launch.cmd_relax, options)
    assert re.search(r'.*Submitted GaussianCommonRelaxWorkChain<.*> to the daemon.*', result.output)


def test_relax_wallclock_seconds(run_cli_command, generate_structure, generate_code):
    """Test the `--wallclock-seconds` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-w` should raise as only one value is required
    options = ['-S', str(structure.pk), '-w', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_relax, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --wallclock-seconds: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


def test_relax_number_machines(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-m', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_relax, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-machines: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


def test_relax_number_mpi_procs_per_machine(run_cli_command, generate_structure, generate_code):
    """Test the `--number-mpi-procs-per-machine` option."""
    structure = generate_structure().store()
    code = generate_code('quantumespresso.pw')
    code.computer.set_default_mpiprocs_per_machine(2)
    code.store()

    # Passing two values for `-n` should raise as only one value is required
    options = ['-S', str(structure.pk), '-n', '10', '10', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_relax, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-mpi-procs-per-machine: QuantumEspressoCommonRelaxWorkChain has 1 engine '
        'steps, so requires 1 values' in result.output_lines
    )


@pytest.mark.usefixtures('with_clean_database')
def test_relax_codes(run_cli_command, generate_structure, generate_code, monkeypatch):
    """Test the `--codes` option."""

    def launch_process(_, __):
        pass

    monkeypatch.setattr(utils, 'launch_process', launch_process)
    structure = generate_structure().store()

    # No codes available
    options = ['-S', str(structure.pk), 'fleur']
    result = run_cli_command(launch.cmd_relax, options, raises=click.UsageError)
    assert 'could not find a configured code for the plugin' in result.output

    code_fleur = generate_code('fleur.fleur').store()
    code_inpgen = generate_code('fleur.inpgen').store()

    # Passing two codes explicitly
    options = ['-S', str(structure.pk), '-X', str(code_fleur.uuid), str(code_inpgen.uuid), '--', 'fleur']
    result = run_cli_command(launch.cmd_relax, options)

    # Passing one code explicitly
    options = ['-S', str(structure.pk), '-X', str(code_fleur.uuid), '--', 'fleur']
    result = run_cli_command(launch.cmd_relax, options)


@pytest.mark.usefixtures('aiida_profile')
def test_eos(run_cli_command, generate_structure, generate_code):
    """Test the `launch eos` command."""
    structure = generate_structure().store()
    generate_code('gaussian').store()

    options = ['-S', str(structure.pk), '-d', 'gaussian']
    result = run_cli_command(launch.cmd_eos, options)
    assert re.search(r'.*Submitted EquationOfStateWorkChain<.*> to the daemon.*', result.output)


def test_eos_wallclock_seconds(run_cli_command, generate_structure, generate_code):
    """Test the `--wallclock-seconds` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-w` should raise as only one value is required
    options = ['-S', str(structure.pk), '-w', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_eos, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --wallclock-seconds: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


def test_eos_number_machines(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-m', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_eos, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-machines: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


def test_eos_number_mpi_procs_per_machine(run_cli_command, generate_structure, generate_code):
    """Test the `--number-mpi-procs-per-machine` option."""
    structure = generate_structure().store()
    code = generate_code('quantumespresso.pw')
    code.computer.set_default_mpiprocs_per_machine(2)
    code.store()

    # Passing two values for `-n` should raise as only one value is required
    options = ['-S', str(structure.pk), '-n', '10', '10', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_eos, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-mpi-procs-per-machine: QuantumEspressoCommonRelaxWorkChain has 1 engine '
        'steps, so requires 1 values' in result.output_lines
    )


def test_eos_relax_types(run_cli_command, generate_structure, generate_code):
    """Test the `--relax-type` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Test that a non-sensical relax type raises
    options = ['-S', str(structure.pk), '-r', 'cell', 'quantum_espresso']
    result = run_cli_command(launch.cmd_eos, options, raises=click.BadParameter)
    assert "Error: Invalid value for '-r' / '--relax-type': 'cell' is not one of " in result.output


def test_dissociation_curve_wallclock_seconds(run_cli_command, generate_structure, generate_code):
    """Test the `--wallclock-seconds` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-w` should raise as only one value is required
    options = ['-S', str(structure.pk), '-w', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_dissociation_curve, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --wallclock-seconds: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


@pytest.mark.usefixtures('aiida_profile')
def test_dissociation_curve(run_cli_command, generate_structure, generate_code):
    """Test the `launch dissociation-curve` command."""
    structure = generate_structure(symbols=['N', 'N']).store()
    generate_code('gaussian').store()

    options = ['-S', str(structure.pk), '-d', 'gaussian']
    result = run_cli_command(launch.cmd_dissociation_curve, options)
    assert re.search(r'.*Submitted DissociationCurveWorkChain<.*> to the daemon.*', result.output)


def test_dissociation_curve_number_machines(run_cli_command, generate_structure, generate_code):
    """Test the `--number-machines` option."""
    structure = generate_structure().store()
    generate_code('quantumespresso.pw').store()

    # Passing two values for `-m` should raise as only one value is required
    options = ['-S', str(structure.pk), '-m', '100', '100', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_dissociation_curve, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-machines: QuantumEspressoCommonRelaxWorkChain has 1 engine steps, so '
        'requires 1 values' in result.output_lines
    )


def test_dissociation_curve_number_mpi_procs_per_machine(run_cli_command, generate_structure, generate_code):
    """Test the `--number-mpi-procs-per-machine` option."""
    structure = generate_structure().store()
    code = generate_code('quantumespresso.pw')
    code.computer.set_default_mpiprocs_per_machine(2)
    code.store()

    # Passing two values for `-n` should raise as only one value is required
    options = ['-S', str(structure.pk), '-n', '10', '10', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_dissociation_curve, options, raises=click.BadParameter)
    assert (
        'Error: Invalid value for --number-mpi-procs-per-machine: QuantumEspressoCommonRelaxWorkChain has 1 engine '
        'steps, so requires 1 values' in result.output_lines
    )


def test_relax_magn_per_type(run_cli_command, generate_structure, generate_code):
    """Test the `--magnetization-per-site` option."""
    structure = generate_structure()
    structure.append_atom(position=(0.000, 0.000, 0.468), symbols=['H'])
    structure.append_atom(position=(0.000, 0.000, 0.268), symbols=['H'])
    structure.store()
    generate_code('quantumespresso.pw').store()

    # Test that only `float` are admissible
    options = ['-S', str(structure.pk), '--magnetization-per-site', 'str', '--', 'quantum_espresso']
    result = run_cli_command(launch.cmd_relax, options, raises=click.BadParameter)
    assert "Error: Invalid value for '--magnetization-per-site': 'str' is not a valid float." in result.output
