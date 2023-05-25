# -*- coding: utf-8 -*-
"""Module with common properties."""
import enum


class PhononProperty(enum.Enum):
    """Enumeration to indicate the phonon properties to extract for a system."""

    NONE = None
    BANDS = {'band': 'auto'}
    DOS = {'dos': True, 'mesh': 1000, 'write_mesh': False}
    THERMODYNAMIC = {'tprop': True, 'mesh': 1000, 'write_mesh': False}
