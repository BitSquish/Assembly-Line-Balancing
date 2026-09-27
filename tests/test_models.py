"""I modelli PLI devono restituire l'ottimo esatto su istanze risolvibili a forza bruta."""

from __future__ import annotations

import pytest

from src.models import NaiveModel, RittCostaModel
from src.solution import Status, is_feasible
from tests.helpers import brute_force_optimum
from tests.test_bounds import _random_instance


@pytest.mark.parametrize("Model", [NaiveModel, RittCostaModel])
def test_ottimo_uguale_alla_forza_bruta(Model):
    for seed in range(40):
        for m, p in ((2, 0.2), (3, 0.3), (4, 0.5)):
            inst = _random_instance(seed, n=7, m=m, p=p)
            res = Model(inst).solve(time_limit=30)
            
            assert res.status is Status.OPTIMAL, (inst, res)
            assert is_feasible(res.solution)
            assert res.objective == res.lower_bound == brute_force_optimum(inst), (inst, res)


@pytest.mark.parametrize("Model", [NaiveModel, RittCostaModel])
def test_upper_bound_esterno_restringe_il_modello(Model):
    inst = _random_instance(3, n=7, m=3)
    opt = brute_force_optimum(inst)
    
    largo = Model(inst)
    stretto = Model(inst, upper_bound=opt)
    
    assert stretto.c_max <= largo.c_max
    assert stretto.solve(time_limit=30).objective == opt