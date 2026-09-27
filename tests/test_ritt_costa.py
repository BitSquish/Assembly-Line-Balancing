"""Il modello deve restituire l'ottimo esatto su istanze risolvibili a forza bruta."""

from __future__ import annotations

from src.models import RittCostaModel
from src.solution import Status, is_feasible
from tests._brute import brute_force_optimum
from tests.test_bounds import _random_instance


def test_ottimo_uguale_alla_forza_bruta():
    for seed in range(40):
        for m, p in ((2, 0.2), (3, 0.3), (4, 0.5)):
            inst = _random_instance(seed, n=7, m=m, p=p)
            res = RittCostaModel(inst).solve(time_limit=30)
            assert res.status is Status.OPTIMAL, (inst, res)
            assert is_feasible(res.solution)
            assert res.objective == res.lower_bound == brute_force_optimum(inst), (inst, res)


def test_upper_bound_esterno_restringe_il_modello():
    inst = _random_instance(3, n=7, m=3)
    opt = brute_force_optimum(inst)
    largo = RittCostaModel(inst)
    stretto = RittCostaModel(inst, upper_bound=opt)
    assert stretto.c_max <= largo.c_max
    assert stretto.solve(time_limit=30).objective == opt