"""Euristica di riferimento: costruzione per stazioni con peso posizionale (RPW).

Riferimenti:
    Helgeson, W. B., & Birnie, D. P. (1961). Assembly line balancing using the
        ranked positional weight technique. Journal of Industrial Engineering.
    Scholl, A., & Becker, C. (2006). State-of-the-art exact and heuristic
        solution procedures for simple assembly line balancing. European
        Journal of Operational Research, 168(3), 666-693. Sez. 5 (regole di
        priorità, procedure station-oriented) e sez. 4.2.1 (ricerca sul tempo
        ciclo per il SALBP-2, "lower bound search").

Idea, in due livelli:

1. Con un tempo ciclo c fissato, si riempiono le stazioni una alla volta.
   Tra i task disponibili (tutti i predecessori già assegnati) che entrano
   nella capacità residua, si sceglie quello con il peso posizionale più alto:
       RPW_i = t_i + somma dei tempi di tutti i successori (diretti e indiretti)
   cioè quanto lavoro "dipende" da i. Quando nessun task entra, si apre la
   stazione successiva. Se servono più di m stazioni, c non basta.

2. Per il SALBP-2 si prova c = LB, LB + 1, LB + 2, ... e ci si ferma al primo
   valore per cui bastano m stazioni.

Non è un metodo esatto: il riempimento è miope, quindi può fallire con un c
per cui una soluzione esiste. Se però trova c uguale al lower bound, la
soluzione è ottima e lo stato lo riporta.
"""

from __future__ import annotations

import time

from ..bounds import StationBounds, lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from ..solution import Solution, SolveResult, Status, violations


def positional_weights(graph: PrecedenceGraph) -> tuple[int, ...]:
    """RPW_i = t_i + somma dei tempi dei successori. Coincide con StationBounds.tail."""
    return StationBounds.from_graph(graph).tail


def fill_stations(
    instance: ALBInstance,
    graph: PrecedenceGraph,
    priority: tuple[int, ...],
    c: int,
) -> tuple[int, ...] | None:
    """Riempie le stazioni con tempo ciclo c. Restituisce stations[i] (1..m) o None.

    A parità di priorità si preferisce il task più lungo, poi l'indice più
    basso: così il risultato è deterministico e riproducibile.
    """
    n, m = instance.n_tasks, instance.m_stations
    t = instance.task_times
    missing_preds = [len(graph.predecessors(i)) for i in range(n)]
    available = {i for i in range(n) if missing_preds[i] == 0}
    stations = [0] * n

    station, load, assigned = 1, 0, 0
    while assigned < n:
        fitting = [i for i in available if load + t[i] <= c]
        if not fitting:
            station, load = station + 1, 0
            if station > m:
                return None
            continue
        i = max(fitting, key=lambda k: (priority[k], t[k], -k))
        stations[i] = station
        load += t[i]
        assigned += 1
        available.remove(i)
        for j in graph.successors(i):
            missing_preds[j] -= 1
            if missing_preds[j] == 0:
                available.add(j)
    return tuple(stations)


def solve(instance: ALBInstance, graph: PrecedenceGraph | None = None) -> SolveResult:
    """RPW con ricerca del tempo ciclo dal lower bound verso l'alto."""
    t0 = time.perf_counter()
    graph = graph or PrecedenceGraph(instance)
    priority = positional_weights(graph)
    lb = lower_bound(instance, graph)

    # c = somma dei tempi funziona sempre (tutto in una stazione): il ciclo termina.
    for c in range(lb, instance.total_time + 1):
        stations = fill_stations(instance, graph, priority, c)
        if stations is not None:
            break

    solution = Solution(instance, stations)
    if errs := violations(solution):
        raise RuntimeError(f"{instance.name}: soluzione RPW non ammissibile: {errs[:5]}")

    objective = solution.max_load
    return SolveResult(
        method="rpw",
        instance_name=instance.name,
        status=Status.OPTIMAL if objective == lb else Status.FEASIBLE,
        objective=objective,
        lower_bound=lb,
        time_s=time.perf_counter() - t0,
        solution=solution,
        extra={"tried_cycle_times": c - lb + 1},
    )