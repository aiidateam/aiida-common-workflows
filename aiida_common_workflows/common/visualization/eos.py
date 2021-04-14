# -*- coding: utf-8 -*-
"""Utilities to fit and visualize a Equation of States based on set of volumes and energies."""
import typing
import numpy

import pylab as plt


def birch_murnaghan(V, E0, V0, B0, B01):
    """Compute energy by Birch Murnaghan formula."""
    # pylint: disable=invalid-name
    r = (V0 / V)**(2. / 3.)
    return E0 + 9. / 16. * B0 * V0 * (r - 1.)**2 * (2. + (B01 - 4.) * (r - 1.))


def fit_birch_murnaghan_params(volumes, energies):
    """Fit Birch Murnaghan parameters."""
    # pylint: disable=invalid-name
    from scipy.optimize import curve_fit

    params, covariance = curve_fit(  # pylint: disable=unbalanced-tuple-unpacking
        birch_murnaghan,
        xdata=volumes,
        ydata=energies,
        p0=(
            energies.min(),  # E0
            volumes.mean(),  # V0
            0.1,  # B0
            3.,  # B01
        ),
        sigma=None
    )
    return params, covariance


def get_eos_plot(
    volumes: typing.List[float],
    energies: typing.List[float],
    unit_volume: str = 'Å^3',
    unit_energy: str = 'eV'
) -> plt:
    """Plot the Equation of State for a given set of volumes and energies

    :param volumes: list of cell volumes.
    :param energies: list of energies.
    :param unit_volume: unit of volume, default is [Å^3].
    :param unit_energy: unit of energy, default is [eV].
    """
    params, _ = fit_birch_murnaghan_params(numpy.array(volumes), numpy.array(energies))

    volume_min = min(volumes)
    volume_max = max(volumes)
    volume_range = numpy.linspace(volume_min, volume_max, 300)

    plt.plot(volumes, energies, 'o')
    plt.plot(volume_range, birch_murnaghan(volume_range, *params))

    plt.xlabel(f'Volume [{unit_volume}]')
    plt.ylabel(f'Energy [{unit_energy}]')

    return plt
