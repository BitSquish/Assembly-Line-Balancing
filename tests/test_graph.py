"""Test per PrecedenceGraph.

Usa un grafo di 10 task costruito a mano, con una struttura simile a quella
degli esempi di Scholl & Becker (2006) ma con tempi e archi propri: i valori
attesi nei test sono stati verificati a mano su questo grafo.
"""

from __future__ import annotations

import pytest

from src.graph import PrecedenceGraph
from src.instance import ALBInstance


def _example_instance() -> ALBInstance:
    # Grafo di esempio (task 1..10 -> indici 0..9):
    # 1->2, 1->3, 2->4, 3->5, 3->7, 4->5, 5->6, 5->8, 5->9, 6->10
    return ALBInstance(
        name="fig1",
        task_times=(6, 6, 2, 2, 8, 7, 4, 
        5, 9, 2),
        precedences=(
            (0, 1), (0, 2),
            (1, 3),
            (2, 4), (2, 6),
            (3, 4),
            (4, 5), (4, 7), (4, 8),
            (5, 9),
        ),
        m_stations=5,
    )


def test_predecessors_and_successors_diretti():
    g = PrecedenceGraph(_example_instance())
    assert g.predecessors(4) == frozenset({2, 3})   # task 5: predecessori 3 e 4
    assert g.successors(4) == frozenset({5, 7, 8})  # task 5: successori 6, 8, 9


def test_chiusura_transitiva():
    g = PrecedenceGraph(_example_instance())
    # task 0 (1) precede tutto ciò che discende da lui, anche indirettamente
    assert g.all_successors(0) == frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9})
    # task 9 (10) non ha nessun successore
    assert g.all_successors(9) == frozenset()
    assert g.precedes(0, 9)       # 1 precede (indirettamente) 10
    assert not g.precedes(9, 0)   # non vale il contrario
    assert g.precedes(0, 0)       # riflessivo per convenzione (i <= i)


def test_riduzione_transitiva_toglie_solo_archi_ridondanti():
    inst = ALBInstance(
        name="ridondante",
        task_times=(1, 1, 1),
        # 0->1, 1->2, 0->2: l'ultimo arco è ridondante (dedotto da 0->1->2)
        precedences=((0, 1), (1, 2), (0, 2)),
        m_stations=2,
    )
    g = PrecedenceGraph(inst)
    assert set(g.reduction) == {(0, 1), (1, 2)}
    # la chiusura transitiva non cambia rimuovendo l'arco ridondante
    assert g.precedes(0, 2)


def test_ordinamento_topologico_rispetta_le_precedenze():
    g = PrecedenceGraph(_example_instance())
    order = g.topological_order
    position = {task: idx for idx, task in enumerate(order)}
    for u, v in _example_instance().precedences:
        assert position[u] < position[v]


def test_order_strength_grafo_completo_vale_1():
    # catena 0->1->2->3: ogni coppia è ordinata, OS deve valere 1.0
    inst = ALBInstance(
        name="catena",
        task_times=(1, 1, 1, 1),
        precedences=((0, 1), (1, 2), (2, 3)),
        m_stations=2,
    )
    g = PrecedenceGraph(inst)
    assert g.order_strength == pytest.approx(1.0)


def test_order_strength_nessuna_precedenza_vale_0():
    inst = ALBInstance(
        name="disconnesso",
        task_times=(1, 1, 1, 1),
        precedences=(),
        m_stations=2,
    )
    g = PrecedenceGraph(inst)
    assert g.order_strength == pytest.approx(0.0)


def test_ciclo_viene_rifiutato():
    inst = ALBInstance(
        name="ciclico",
        task_times=(1, 1, 1),
        precedences=((0, 1), (1, 2), (2, 0)),
        m_stations=1,
    )
    with pytest.raises(ValueError, match="ciclo"):
        PrecedenceGraph(inst)