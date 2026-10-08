"""Euristiche per il SALBP-2, con la stessa interfaccia dei PLI: solve(...) -> SolveResult.

- groups:   euristica dei gruppi, sviluppata nel progetto;
- hoffmann: saturazione delle stazioni (Hoffmann, 1963) adattata al SALBP-2.
"""

from . import groups, hoffmann

__all__ = ["groups", "hoffmann"]