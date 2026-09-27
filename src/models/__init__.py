"""Modelli PLI per il SALBP-2, con interfaccia comune solve(time_limit) -> SolveResult."""

from .ritt_costa import RittCostaModel
from .naive import NaiveModel
# from .patterson import PattersonModel  # Lo decommenteremo appena lo creiamo

__all__ = [
    "RittCostaModel",
    "NaiveModel",
    # "PattersonModel",
]