"""Test per bounds.py: ogni bound deve stare dal lato giusto dell'ottimo."""

from __future__ import annotations

import random

from src.bounds import StationBounds, greedy_solution, lower_bound, simple_lower_bound
from src.graph import PrecedenceGraph
from src.instance import ALBInstance
from src.solution import is_feasible
from tests.test_brute import brute_force_optimum


def _random_instance(seed: int, n: int = 7, m: int = 3, p: float = 0.3) -> ALBInstance:
    rng = random.Random(seed)
    times = [rng.randint(1, 10) for _ in range(n)]
    prec = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    return ALBInstance(f"rnd{seed}", times, prec, m_stations=m)


def test_simple_lower_bound_esempio_a_mano():
    # tempi 9, 8, 3, 2 su m = 2: media ceil(22/2) = 11,
    # k = 1: tra i 3 più lunghi (9, 8, 3) due stanno insieme -> 8 + 3 = 11.
    inst = ALBInstance("lb", (9, 8, 3, 2), (), m_stations=2)
    assert simple_lower_bound(inst) == 11


def test_finestre_su_catena():
    # catena 0 -> 1 -> 2 con tempi 4, 4, 4, m = 3, c = 4: una stazione per task
    inst = ALBInstance("catena", (4, 4, 4), ((0, 1), (1, 2)), m_stations=3)
    sb = StationBounds.from_graph(PrecedenceGraph(inst))
    assert [sb.earliest(i, 4) for i in range(3)] == [1, 2, 3]
    assert [sb.latest(i, 4) for i in range(3)] == [1, 2, 3]
    # con c = 8 le finestre si allargano
    assert (sb.earliest(2, 8), sb.latest(0, 8)) == (2, 2)
    # con c = 3 il task 2 non entra nella linea
    assert not sb.windows_nonempty(3)


def test_bound_validi_su_istanze_casuali():
    for seed in range(40):
        inst = _random_instance(seed)
        g = PrecedenceGraph(inst)
        opt = brute_force_optimum(inst)
        greedy = greedy_solution(inst, g)
        assert is_feasible(greedy)
        assert simple_lower_bound(inst) <= lower_bound(inst, g) <= opt <= greedy.max_load