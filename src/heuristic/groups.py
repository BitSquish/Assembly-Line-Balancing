"""Euristica dei gruppi per il SALBP-2.

Idea: le operazioni legate da precedenze vicine tendono a stare nella stessa
stazione o in stazioni consecutive. L'euristica le raccoglie in gruppi, li
dispone lungo la linea nell'ordine imposto dalle precedenze, e usa le foglie
del grafo (operazioni senza successori) come riempitivi per bilanciare i
carichi.

1. Foglie. Le operazioni senza successori non entrano nei gruppi: restano
   libere e servono da riempitivi. Un'operazione isolata, senza predecessori
   né successori, è anch'essa una foglia.

2. Gruppi. Sulle operazioni restanti si formano i gruppi, a ondate:
     - le radici dell'ondata sono le operazioni i cui predecessori (foglie
       escluse) sono già tutti in un gruppo; si considerano in ordine di peso
       posizionale decrescente (tempo dell'operazione più quello di tutti i
       suoi successori);
     - ogni radice forma un gruppo insieme ai suoi figli diretti, purché
       ogni figlio abbia tutti gli altri predecessori già in un gruppo;
     - le operazioni rimaste senza gruppo passano all'ondata successiva.
   Ogni operazione sta in un solo gruppo. Per costruzione un gruppo dipende
   solo da gruppi formati prima: il grafo dei gruppi è aciclico.

3. Grafo dei gruppi. C'è un arco dal gruppo A al gruppo B se un'operazione di
   B ha un predecessore in A. Il livello di un gruppo è la lunghezza del
   cammino più lungo che vi arriva (0 per i gruppi senza archi entranti).
   Priorità dei gruppi: livello crescente, poi costo decrescente.

4. Riempimento delle stazioni, con un tempo ciclo di prova c:
     - a ogni passo i candidati sono
         * il primo gruppo, in ordine di priorità, di cui almeno la prossima
           operazione ha i predecessori già piazzati e sta nello spazio
           rimasto; se il gruppo non ci sta per intero lo si spezza,
           prendendo le sue prime operazioni in ordine topologico finché
           stanno nello spazio rimasto;
         * le foglie disponibili (predecessori già piazzati) che ci stanno;
     - vince il candidato che porta il carico più vicino a c senza
       superarlo; a parità, il gruppo;
     - quando nessun candidato ci sta si passa alla stazione successiva.

5. Tempo ciclo. Si parte da c = LB (bounds.py). Se dopo m stazioni restano
   operazioni da piazzare, si riprova con c + 1: la prima soluzione trovata
   è quella restituita. È lo stesso ciclo esterno dell'euristica di Hoffmann
   (hoffmann.py), così il confronto tra le due misura solo il criterio di
   riempimento delle stazioni.

L'euristica è stata sviluppata nel progetto a partire da una versione per
layer del grafo delle precedenze.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..bounds import StationBounds, lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from ..solution import Solution, SolveResult, Status, violations


@dataclass(frozen=True, slots=True)
class Groups:
    """Risultato della scomposizione (passi 1-3).

    tasks[g]: operazioni del gruppo g in ordine topologico;
    leaves:   foglie, dalla più lunga alla più corta;
    order:    indici dei gruppi in ordine di priorità.
    """

    tasks: tuple[tuple[int, ...], ...]
    leaves: tuple[int, ...]
    order: tuple[int, ...]


def build_groups(graph: PrecedenceGraph) -> Groups:
    """Passi 1-3: foglie, gruppi a ondate e ordine di priorità dei gruppi."""
    inst = graph.instance
    n, t = inst.n_tasks, inst.task_times
    weight = StationBounds.from_graph(graph).tail          # peso posizionale
    topo_pos = {task: k for k, task in enumerate(graph.topological_order)}

    is_leaf = [not graph.successors(i) for i in range(n)]
    leaves = tuple(sorted((i for i in range(n) if is_leaf[i]), key=lambda i: (-t[i], i)))

    group_of = [-1] * n
    groups: list[list[int]] = []
    remaining = {i for i in range(n) if not is_leaf[i]}

    def ready(i: int) -> bool:
        # Tutti i predecessori sono già in un gruppo (le foglie non sono mai
        # predecessori: non hanno successori per definizione).
        return all(group_of[p] >= 0 for p in graph.predecessors(i))

    while remaining:
        roots = sorted((i for i in remaining if ready(i)), key=lambda i: (-weight[i], i))
        for root in roots:
            if group_of[root] >= 0:           # preso come figlio in questa ondata
                continue
            g = len(groups)
            members = [root]
            group_of[root] = g
            for child in sorted(graph.successors(root), key=lambda i: topo_pos[i]):
                if child in remaining and group_of[child] < 0 and all(
                    group_of[p] >= 0 for p in graph.predecessors(child)
                ):
                    members.append(child)
                    group_of[child] = g
            groups.append(sorted(members, key=lambda i: topo_pos[i]))
        remaining = {i for i in remaining if group_of[i] < 0}

    # Grafo dei gruppi e livelli. Gli archi vanno sempre da un gruppo formato
    # prima a uno formato dopo, quindi basta scorrerli in ordine di creazione.
    level = [0] * len(groups)
    for g, members in enumerate(groups):
        for i in members:
            for p in graph.predecessors(i):
                h = group_of[p]
                if h != g:
                    level[g] = max(level[g], level[h] + 1)

    cost = [sum(t[i] for i in members) for members in groups]
    order = tuple(sorted(range(len(groups)), key=lambda g: (level[g], -cost[g], g)))
    return Groups(tasks=tuple(tuple(m) for m in groups), leaves=leaves, order=order)


def _assign_with_cycle_time(
    instance: ALBInstance, graph: PrecedenceGraph, groups: Groups, c: int
) -> tuple[int, ...] | None:
    """Passo 4: stazione di ogni operazione se c basta con m stazioni, altrimenti None."""
    n, m, t = instance.n_tasks, instance.m_stations, instance.task_times
    preds = [graph.predecessors(i) for i in range(n)]
    stations = [0] * n
    next_in_group = [0] * len(groups.tasks)      # prima operazione non piazzata

    def available(i: int) -> bool:
        return stations[i] == 0 and all(stations[p] for p in preds[i])

    for s in range(1, m + 1):
        load = 0
        while True:
            space = c - load

            # Candidato gruppo: il primo, in ordine di priorità, di cui si riesce
            # a piazzare almeno la prima operazione ancora in sospeso.
            best_unit: list[int] = []
            for g in groups.order:
                members = groups.tasks[g]
                k = next_in_group[g]
                unit, used = [], 0
                while k < len(members):
                    i = members[k]
                    ok_preds = all(stations[p] or p in unit for p in preds[i])
                    if not ok_preds or used + t[i] > space:
                        break
                    unit.append(i)
                    used += t[i]
                    k += 1
                if unit:
                    best_unit = unit
                    break

            # Candidato foglia: la più lunga disponibile che ci sta.
            best_leaf = next(
                (i for i in groups.leaves if available(i) and t[i] <= space), None
            )

            unit_load = sum(t[i] for i in best_unit)
            leaf_load = t[best_leaf] if best_leaf is not None else 0
            if not best_unit and best_leaf is None:
                break                                   # stazione chiusa
            if best_unit and unit_load >= leaf_load:
                for i in best_unit:
                    stations[i] = s
                g = next(g for g in groups.order if best_unit[0] in groups.tasks[g])
                next_in_group[g] += len(best_unit)
                load += unit_load
            else:
                stations[best_leaf] = s
                load += leaf_load

    return tuple(stations) if all(stations) else None


def solve(instance: ALBInstance, graph: PrecedenceGraph | None = None) -> SolveResult:
    """Euristica dei gruppi con ricerca del tempo ciclo dal lower bound (passo 5)."""
    t0 = time.perf_counter()
    graph = graph or PrecedenceGraph(instance)
    groups = build_groups(graph)
    lb = lower_bound(instance, graph)

    # c = somma dei tempi funziona sempre (tutto in una stazione): il ciclo termina.
    for c in range(lb, instance.total_time + 1):
        stations = _assign_with_cycle_time(instance, graph, groups, c)
        if stations is not None:
            break

    solution = Solution(instance, stations)
    if errs := violations(solution):
        raise RuntimeError(f"{instance.name}: soluzione non ammissibile: {errs[:5]}")

    objective = solution.max_load
    return SolveResult(
        method="gruppi",
        instance_name=instance.name,
        status=Status.OPTIMAL if objective == lb else Status.FEASIBLE,
        objective=objective,
        lower_bound=lb,
        time_s=time.perf_counter() - t0,
        solution=solution,
        extra={
            "tried_cycle_times": c - lb + 1,
            "n_groups": len(groups.tasks),
            "n_leaves": len(groups.leaves),
        },
    )