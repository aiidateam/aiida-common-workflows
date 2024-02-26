"""Module with basic type definitions."""
from enum import Enum

__all__ = ('ElectronicType', 'SpinType', 'RelaxType')


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
    SPIN_ORBIT = 'spin_orbit'


class ElectronicType(Enum):
    """Enumeration of known electronic types."""

    AUTOMATIC = 'automatic'
    METAL = 'metal'
    INSULATOR = 'insulator'
    UNKNOWN = 'unknown'
