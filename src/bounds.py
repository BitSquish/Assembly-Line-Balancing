"""Lower bound, upper bound e finestre di stazione per il SALBP-2.

Convenzione: le stazioni sono numerate 1..m, come nei paper. Così E_i e L_i
calcolati qui coincidono con le formule di Ritt & Costa senza traslazioni.

Finestre di stazione per un tempo ciclo c (Scholl & Becker, 2006, sez. 3.1):

    E_i(c) = ceil( (t_i + somma dei tempi di P*_i) / c )
    L_i(c) = m + 1 - ceil( (t_i + somma dei tempi di F*_i) / c )

E_i: prima di i vanno eseguiti tutti i suoi predecessori, e ogni stazione
ne contiene al massimo c; L_i: simmetrico sui successori. Se in una soluzione
ogni stazione ha carico <= c, ogni task i sta in [E_i(c), L_i(c)].
E_i è non crescente in c e L_i non decrescente: a c più grande, finestre
più larghe.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import PrecedenceGraph
from .instance import ALBInstance
from .solution import Solution


def _ceil_div(a: int, b: int) -> int:
    """ceil(a / b) per interi positivi, senza passare dai float."""
    return -(-a // b)


@dataclass(frozen=True, slots=True, repr=False)
class StationBounds:
    """Calcolo di E_i(c) e L_i(c) per qualsiasi tempo ciclo c.

    head[i] = t_i + somma dei tempi dei predecessori (diretti e indiretti);
    tail[i] = t_i + somma dei tempi dei successori (diretti e indiretti).
    Si calcolano una volta sola: poi ogni finestra costa O(1).
    """

    m: int
    head: tuple[int, ...]
    tail: tuple[int, ...]

    @classmethod
    def from_graph(cls, graph: PrecedenceGraph) -> StationBounds:
        inst = graph.instance
        t = inst.task_times
        head = tuple(
            t[i] + sum(t[h] for h in graph.all_predecessors(i))
            for i in range(inst.n_tasks)
        )
        tail = tuple(
            t[i] + sum(t[h] for h in graph.all_successors(i))
            for i in range(inst.n_tasks)
        )
        return cls(m=inst.m_stations, head=head, tail=tail)

    def __repr__(self) -> str:
        return f"StationBounds(n={len(self.head)}, m={self.m})"

    def earliest(self, i: int, c: int) -> int:
        """E_i(c): prima stazione ammissibile per il task i con tempo ciclo c."""
        return _ceil_div(self.head[i], c)

    def latest(self, i: int, c: int) -> int:
        """L_i(c): ultima stazione ammissibile per il task i con tempo ciclo c."""
        return self.m + 1 - _ceil_div(self.tail[i], c)

    def windows_nonempty(self, c: int) -> bool:
        """True se ogni task ha almeno una stazione ammissibile con tempo ciclo c.

        Se è False, nessuna soluzione ha carico massimo <= c: c non è
        raggiungibile, e quindi c + 1 è un lower bound valido.
        """
        return all(
            self.earliest(i, c) <= self.latest(i, c) for i in range(len(self.head))
        )


# ------------------------------------------------------------------ lower bound


def simple_lower_bound(instance: ALBInstance) -> int:
    """Massimo tra i bound combinatori classici sul carico massimo.

    - ceil(somma dei tempi / m): il carico medio;
    - per k = 0, 1, 2, ...: tra i k*m + 1 task più lunghi, per il principio
      dei cassetti almeno k + 1 finiscono nella stessa stazione, quindi
      c >= somma dei k + 1 più corti tra questi.
      k = 0 dà t_max, k = 1 dà t_(m) + t_(m+1) (tempi in ordine decrescente).
    """
    m = instance.m_stations
    t = sorted(instance.task_times, reverse=True)
    best = _ceil_div(instance.total_time, m)
    k = 0
    while k * m + 1 <= len(t):
        top = k * m + 1                    # numero di task più lunghi considerati
        best = max(best, sum(t[top - k - 1 : top]))
        k += 1
    return best


def lower_bound(
    instance: ALBInstance,
    graph: PrecedenceGraph | None = None,
    upper_bound: int | None = None,
) -> int:
    """Lower bound sul carico massimo ottimo.

    Parte dai bound combinatori e poi lo alza finché le finestre di stazione
    non sono tutte non vuote (vedi StationBounds.windows_nonempty).
    upper_bound serve solo a fermare la ricerca: non si va oltre.
    """
    graph = graph or PrecedenceGraph(instance)
    sb = StationBounds.from_graph(graph)
    lb = simple_lower_bound(instance)
    stop = upper_bound if upper_bound is not None else instance.total_time
    while lb < stop and not sb.windows_nonempty(lb):
        lb += 1
    return lb


# ------------------------------------------------------------------ upper bound


def greedy_solution(
    instance: ALBInstance, graph: PrecedenceGraph | None = None
) -> Solution:
    """Soluzione ammissibile banale, usata come upper bound iniziale.

    Scorre i task in ordine topologico e riempie le stazioni in sequenza,
    chiudendo una stazione appena il suo carico raggiunge la media
    somma/m. Ogni stazione chiusa ha carico >= somma/m, quindi se ne chiudono
    al massimo m - 1 prima di arrivare all'ultima, che raccoglie il resto.
    Le precedenze sono rispettate perché l'ordine è topologico e l'indice di
    stazione non decresce mai. Carico massimo < somma/m + t_max.

    Non è l'euristica del progetto: serve solo a fissare un c_max valido
    per le finestre del PLI.
    """
    graph = graph or PrecedenceGraph(instance)
    m = instance.m_stations
    target = instance.total_time / m
    stations = [0] * instance.n_tasks
    current, load = 1, 0
    for i in graph.topological_order:
        stations[i] = current
        load += instance.task_times[i]
        if load >= target and current < m:
            current, load = current + 1, 0
    return Solution(instance, tuple(stations))