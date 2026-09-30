"""Euristiche per il SALBP-2, con la stessa interfaccia dei PLI: solve(...) -> SolveResult.

- rpw: euristica di riferimento (peso posizionale, Helgeson & Birnie 1961);
- saturation: euristica di saturazione delle stazioni.
"""

from . import rpw, saturation

__all__ = ["rpw", "saturation"]