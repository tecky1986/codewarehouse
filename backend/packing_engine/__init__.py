"""Packing engine: pure-python cargo-to-container solver.

Coordinates:
  x axis: 0 at the door, increasing toward the inner end wall (x = inner_l).
  y axis: 0..inner_w, z axis: 0..inner_h (z = floor).
Units: mm for dimensions, kg for weights, m3 for volumes.
"""

from packing_engine.model import (
    Candidate,
    CargoItem,
    ContainerInstance,
    Plan,
)
from packing_engine.place import (
    ALGORITHMS,
    dblf,
    maximal_space,
    wall_fill,
)
import packing_engine.place2  # noqa: F401  (registers extra algorithms)
from packing_engine.kpi import evaluate
from packing_engine.place import register
from packing_engine.normalize import freemix as _freemix_fn

register("freemix", _freemix_fn)

__all__ = [
    "ALGORITHMS",
    "Candidate",
    "CargoItem",
    "ContainerInstance",
    "Plan",
    "dblf",
    "extreme_point",
    "guillotine",
    "maximal_space",
    "wall_build",
    "wall_fill",
    "evaluate",
]
