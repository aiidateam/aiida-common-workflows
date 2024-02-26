"""Utilities to fit and visualize a Equation of States based on set of volumes and energies."""
import typing

import matplotlib.pyplot as plt
import numpy


def birch_murnaghan(V, E0, V0, B0, B01):  # noqa: N803
    """Compute energy by Birch Murnaghan formula."""

    r = (V0 / V) ** (2.0 / 3.0)
    return E0 + 9.0 / 16.0 * B0 * V0 * (r - 1.0) ** 2 * (2.0 + (B01 - 4.0) * (r - 1.0))


def fit_birch_murnaghan_params(volumes, energies):
    """Fit Birch Murnaghan parameters."""

    from scipy.optimize import curve_fit

    params, covariance = curve_fit(
        birch_murnaghan,
        xdata=volumes,
        ydata=energies,
        p0=(
            energies.min(),  # E0
            volumes.mean(),  # V0
            0.1,  # B0
            3.0,  # B01
        ),
        sigma=None,
    )
    return params, covariance


def get_eos_plot(
    volumes: typing.List[float], energies: typing.List[float], unit_volume: str = 'Å^3', unit_energy: str = 'eV'
) -> plt:
    """Plot the Equation of State for a given set of volumes and energies

    :param volumes: list of cell volumes.
    :param energies: list of energies.
    :param unit_volume: unit of volume, default is [Å^3].
    :param unit_energy: unit of energy, default is [eV].
    """
    if len(volumes) != len(energies):
        raise ValueError('`distances` and `energies` are not of the same length.')
    if any(not isinstance(v, float) for v in volumes):
        raise ValueError('not all values provided in `volumes` are of type `float`.')
    if any(not isinstance(d, float) for d in energies):
        raise ValueError('not all values provided in `energies` are of type `float`.')

    params, _ = fit_birch_murnaghan_params(numpy.array(volumes), numpy.array(energies))

    volume_min = min(volumes)
    volume_max = max(volumes)
    volume_range = numpy.linspace(volume_min, volume_max, 300)

    plt.plot(volumes, energies, 'o')
    plt.plot(volume_range, birch_murnaghan(volume_range, *params))

    plt.xlabel(f'Volume [{unit_volume}]')
    plt.ylabel(f'Energy [{unit_energy}]')

    return plt
