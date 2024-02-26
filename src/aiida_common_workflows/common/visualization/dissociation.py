"""Utilities to visualize a dissociation curve based on set of distances and energies."""
import typing

import matplotlib.pyplot as plt


def get_dissociation_plot(
    distances: typing.List[float], energies: typing.List[float], unit_distance: str = 'Å', unit_energy: str = 'eV'
) -> plt:
    """Plot the dissociation curve for a given set of distances and energies.

    :param distances: list of cell volumes.
    :param energies: list of energies.
    :param unit_distance: unit of distance, default is [Å].
    :param unit_energy: unit of energy, default is [eV].
    """
    if len(distances) != len(energies):
        raise ValueError('`distances` and `energies` are not of the same length.')
    if any(not isinstance(d, float) for d in distances):
        raise ValueError('not all values provided in `distances` are of type `float`.')
    if any(not isinstance(e, float) for e in energies):
        raise ValueError('not all values provided in `energies` are of type `float`.')

    plt.plot(distances, energies, 'o-')

    plt.xlabel(f'Distance [{unit_distance}]')
    plt.ylabel(f'Energy [{unit_energy}]')

    return plt
