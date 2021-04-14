# -*- coding: utf-8 -*-
"""Utilities to visualize a dissociation curve based on set of distances and energies."""
import typing

import matplotlib.pyplot as plt


def get_dissociation_plot(
    distances: typing.List[float],
    energies: typing.List[float],
    unit_distance: str = 'Å^3',
    unit_energy: str = 'eV'
) -> plt:
    """Plot the dissociation curve for a given set of distances and energies.

    :param distances: list of cell volumes.
    :param energies: list of energies.
    :param unit_distance: unit of volume, default is [Å^3].
    :param unit_energy: unit of energy, default is [eV].
    """
    plt.plot(distances, energies, 'o-')

    plt.xlabel(f'Distance [{unit_distance}]')
    plt.ylabel(f'Energy [{unit_energy}]')

    return plt
