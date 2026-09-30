"""Euristiche per il SALBP-2, con la stessa interfaccia dei PLI: solve(...) -> SolveResult.

- groups:   euristica dei gruppi, sviluppata nel progetto;
- hoffmann: euristica di Hoffmann (1963), riferimento dalla letteratura.
"""

from . import groups, hoffmann

__all__ = ["groups", "hoffmann"]