from src.instance import ALBInstance
from src.solution import Solution, SolveResult, Status, violations


def _inst():
    return ALBInstance("s", (10, 12, 9), ((0, 1),), m_stations=3)


def test_carichi_e_carico_massimo():
    sol = Solution(_inst(), (1, 2, 3))
    assert sol.loads == (10, 12, 9)
    assert sol.max_load == 12


def test_violazioni():
    assert violations(Solution(_inst(), (1, 2, 3))) == []
    assert len(violations(Solution(_inst(), (2, 1, 3)))) == 1   # precedenza 0 -> 1
    assert len(violations(Solution(_inst(), (1, 2, 4)))) == 1   # stazione fuori range


def test_gap():
    r = SolveResult("h", "s", Status.FEASIBLE, objective=12, lower_bound=10, time_s=0.1)
    assert abs(r.gap - 0.2) < 1e-12