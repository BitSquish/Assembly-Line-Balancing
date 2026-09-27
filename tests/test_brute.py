"""Ottimo per enumerazione completa, per istanze minuscole (m^n assegnamenti)."""

from itertools import product

from src.instance import ALBInstance


def brute_force_optimum(inst: ALBInstance) -> int:
    best = None
    for stations in product(range(1, inst.m_stations + 1), repeat=inst.n_tasks):
        if any(stations[u] > stations[v] for u, v in inst.precedences):
            continue
        loads = [0] * inst.m_stations
        for i, s in enumerate(stations):
            loads[s - 1] += inst.task_times[i]
        value = max(loads)
        if best is None or value < best:
            best = value
    return best