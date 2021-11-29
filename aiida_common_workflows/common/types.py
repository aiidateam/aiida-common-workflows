# -*- coding: utf-8 -*-
"""Module with basic type definitions."""
from enum import Enum

__all__ = ('ElectronicType', 'SpinType', 'RelaxType', 'OccupationType', 'XcFunctionalType')


class RelaxType(Enum):
    """Enumeration of known relax types."""

    NONE = 'none'
    POSITIONS = 'positions'
    VOLUME = 'volume'
    SHAPE = 'shape'
    CELL = 'cell'
    POSITIONS_CELL = 'positions_cell'
    POSITIONS_VOLUME = 'positions_volume'
    POSITIONS_SHAPE = 'positions_shape'


class SpinType(Enum):
    """Enumeration of known spin types."""

    NONE = 'none'
    COLLINEAR = 'collinear'
    NON_COLLINEAR = 'non_collinear'


class ElectronicType(Enum):
    """Enumeration of known electronic types."""

    UNKNOWN = 'unknown'
    METAL = 'metal'
    INSULATOR = 'insulator'


class OccupationType(Enum):
    """Enumeration of known methods of treating electronic occupations."""

    FIXED = 'fixed'
    TETRAHEDRON = 'tetrahedron'
    GAUSSIAN = 'gaussian'
    FERMI_DIRAC = 'fermi-dirac'
    METHFESSEL_PAXTON = 'methfessel-paxton'
    MARZARI_VANDERBILT = 'marzari-vanderbilt'


class XcFunctionalType(Enum):
    """Enumeration of known exchange-correlation functional types."""

    LDA = 'lda'
    PBE = 'pbe'
    PBESOL = 'pbesol'
