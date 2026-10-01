"""Test per le euristiche: gruppi (sviluppata nel progetto) e Hoffmann (riferimento)."""

from __future__ import annotations

import pytest

from src.graph import PrecedenceGraph
from src.heuristic import groups, hoffmann
from src.instance import ALBInstance
from src.solution import Status, is_feasible
from tests.helpers import brute_force_optimum, random_instance

HEURISTICS = [groups, hoffmann]


def _esempio() -> ALBInstance:
    # L'esempio "su carta" (task 1..10 -> indici 0..9), m = 3. Ottimo 18, LB 17.
    return ALBInstance(
        "esempio",
        (4, 8, 7, 4, 7, 1, 7, 5, 5, 2),
        ((0, 2), (1, 6), (2, 5), (2, 6), (2, 8), (3, 7), (3, 8), (4, 9), (6, 7), (6, 9)),
        m_stations=3,
    )


def test_gruppi_esempio_scomposizione():
    # Foglie 6, 8, 9, 10; gruppi {1, 3}, {2, 7}, {4}, {5} (indici 1-based).
    g = groups.build_groups(PrecedenceGraph(_esempio()))
    assert [sorted(i + 1 for i in grp) for grp in g.tasks] == [[1, 3], [2, 7], [4], [5]]
    assert sorted(i + 1 for i in g.leaves) == [6, 8, 9, 10]


@pytest.mark.parametrize("heuristic", HEURISTICS)
def test_esempio_arriva_all_ottimo(heuristic):
    res = heuristic.solve(_esempio())
    assert res.objective == 18
    assert res.lower_bound == 17
    assert is_feasible(res.solution)


@pytest.mark.parametrize("heuristic", HEURISTICS)
def test_ammissibile_e_mai_sotto_ottimo(heuristic):
    for seed in range(40):
        for m, p in ((2, 0.2), (3, 0.3), (4, 0.5)):
            inst = random_instance(seed, n=7, m=m, p=p)
            res = heuristic.solve(inst)
            opt = brute_force_optimum(inst)
            assert is_feasible(res.solution)
            assert res.lower_bound <= opt <= res.objective
            if res.status is Status.OPTIMAL:
                assert res.objective == opt