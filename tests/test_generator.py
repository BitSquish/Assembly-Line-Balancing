"""Test per il generatore di istanze."""

from __future__ import annotations

import pytest

from src.generator import generate
from src.graph import PrecedenceGraph
from src.instance import ALBInstance


@pytest.mark.parametrize("n, target", [(30, 0.2), (30, 0.6), (100, 0.2), (100, 0.6)])
def test_order_strength_vicina_all_obiettivo(n, target):
    inst = generate(n, n // 4, target, seed=1)
    achieved = PrecedenceGraph(inst).order_strength     # ricalcolata da zero
    assert achieved == pytest.approx(inst.meta["order_strength"])
    assert target <= achieved <= target + 0.02


def test_stesso_seed_stessa_istanza():
    a = generate(40, 8, 0.4, seed=7, time_dist="bimodal")
    b = generate(40, 8, 0.4, seed=7, time_dist="bimodal")
    c = generate(40, 8, 0.4, seed=8, time_dist="bimodal")
    assert a == b
    assert a != c


def test_archi_in_avanti_e_grafo_aciclico():
    inst = generate(50, 10, 0.6, seed=3)
    assert all(u < v for u, v in inst.precedences)
    PrecedenceGraph(inst)                                # solleva se ci fosse un ciclo


@pytest.mark.parametrize("dist", ["uniform", "bimodal"])
def test_tempi_nell_intervallo(dist):
    inst = generate(200, 20, 0.2, seed=5, time_dist=dist, t_min=1, t_max=100)
    assert all(1 <= t <= 100 for t in inst.task_times)


def test_bimodale_ha_molti_tempi_corti():
    inst = generate(500, 50, 0.2, seed=5, time_dist="bimodal", t_min=1, t_max=99)
    short = sum(t <= 33 for t in inst.task_times)
    long_ = sum(t >= 67 for t in inst.task_times)
    assert short + long_ == 500                          # niente nel terzo centrale
    assert 0.7 < short / 500 < 0.9


def test_os_zero_nessun_arco():
    assert generate(20, 4, 0.0, seed=1).precedences == ()


def test_salvataggio_e_rilettura(tmp_path):
    inst = generate(30, 6, 0.4, seed=2)
    inst.save(tmp_path / "x.alb")
    # Il nome di default è quello del file: si passa quello originale per il confronto.
    assert ALBInstance.load(tmp_path / "x.alb", name=inst.name) == inst


def test_parametri_non_validi():
    with pytest.raises(ValueError):
        generate(10, 11, 0.2)
    with pytest.raises(ValueError):
        generate(10, 2, 1.5)
    with pytest.raises(ValueError):
        generate(10, 2, 0.2, time_dist="normale")