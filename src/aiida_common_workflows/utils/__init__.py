""" Some common util functions to be used in other modules."""


def to_spherical(v):
    """Convert a vector from Cartesian (x, y, z) to
    spherical (r, theta, phi) coordinates.

    Note that the angles are returned in degrees.
    """
    import numpy as np

    x, y, z = v
    r = np.linalg.norm(v)
    rxy = np.hypot(x, y)
    theta = np.degrees(np.arctan2(rxy, z))
    phi = np.degrees(np.arctan2(y, x))

    return r, theta, phi
