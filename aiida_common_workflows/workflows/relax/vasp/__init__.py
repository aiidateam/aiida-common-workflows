# -*- coding: utf-8 -*-
# pylint: disable=undefined-variable
"""Module with the implementations of the common structure relaxation workchainm for VASP."""
from .generator import *
from .workchain import *

__all__ = (generator.__all__ + workchain.__all__)
