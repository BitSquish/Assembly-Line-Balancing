"""Saturazione delle stazioni (Hoffmann, 1963) adattata al SALBP-2.

L'euristica cerca il più piccolo tempo ciclo c per cui le m stazioni riescono a
contenere tutte le operazioni, costruendo le stazioni una alla volta e
riempiendo ciascuna il più possibile.

Struttura:

    per c = LB, LB + 1, LB + 2, ...            (LB: lower bound di bounds.py)
        per ogni stazione s = 1, ..., m:
            tra le operazioni disponibili, cioè con tutti i predecessori già
            assegnati, sceglie l'insieme che porta il carico di s il più
            vicino possibile a c senza superarlo (saturazione della stazione)
        se tutte le operazioni sono assegnate: restituisce la soluzione

La saturazione di una stazione è un problema di tipo zaino con vincoli di
precedenza: l'insieme scelto deve essere chiuso rispetto alle precedenze
(un'operazione entra solo insieme ai suoi predecessori non ancora assegnati).
Viene risolto con una ricerca in profondità sugli insiemi ammissibili, con
memoria degli insiemi già visitati. Per contenere i tempi sulle istanze grandi
la ricerca ha un limite di nodi (node_limit): oltre il limite si usa il miglior
insieme trovato fino a quel momento. A parità di carico si tiene il primo
insieme trovato; la ricerca esplora per prime le operazioni più lunghe.

Quando il limite scatta, la stazione può non essere saturata al meglio. Per
sapere quanto spesso succede, il risultato riporta due conteggi (in `extra`):
    node_limit_hits        stazioni della soluzione restituita in cui la
                           ricerca è stata interrotta dal limite;
    node_limit_hits_total  lo stesso conteggio su tutti i tempi ciclo provati,
                           compresi quelli scartati.
Se sono entrambi zero, ogni stazione è stata saturata con una ricerca completa.

Origine e letteratura:
    L'idea di saturare ogni stazione è nata nello sviluppo di questo progetto,
    come evoluzione di due euristiche precedenti (per layer del grafo delle
    precedenze e per gruppi di operazioni). Una verifica sulla letteratura ha
    mostrato che il criterio coincide con l'euristica di Hoffmann:

        Hoffmann, T. R. (1963). Assembly line balancing with a precedence
            matrix. Management Science.

    descritta in Scholl, A., & Becker, C. (2006). State-of-the-art exact and
    heuristic solution procedures for simple assembly line balancing. European
    Journal of Operational Research, 168(3), 666-693, sez. 5.1.2. L'adattamento
    al SALBP-2 tramite ricerca sul tempo ciclo a partire dal lower bound segue
    lo schema delle sez. 4.2.1 e 5.1.3 dello stesso articolo.

    Si sono provati anche criteri di scelta a parità di carico (peso
    posizionale, lavoro sbloccato, operazioni lunghe, rinvio delle foglie come
    riempitivi): nessuno ha migliorato in modo significativo la versione qui
    implementata, a fronte di tempi di calcolo circa cento volte maggiori.
"""

from __future__ import annotations

import time

from ..bounds import lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from ..solution import Solution, SolveResult, Status, violations


def saturate_station(
    task_times: tuple[int, ...],
    successors: list[tuple[int, ...]],
    missing_preds: dict[int, int],
    available: set[int],
    capacity: int,
    node_limit: int,
) -> tuple[list[int], bool]:
    """Insieme di operazioni ammissibile con carico massimo <= capacity.

    Args:
        missing_preds: per ogni operazione non assegnata, quanti predecessori
            mancano ancora; un'operazione diventa disponibile quando arriva a 0.
        available: operazioni già disponibili all'apertura della stazione.

    Returns:
        L'insieme scelto e un indicatore: True se la ricerca è stata interrotta
        dal limite di nodi prima di saturare la stazione, quindi l'insieme
        potrebbe non essere il migliore.

    Un insieme è ammissibile se ogni sua operazione ha tutti i predecessori
    già assegnati o dentro l'insieme stesso. Lo stesso insieme si raggiunge in
    ordini diversi: la memoria `seen` evita di esplorarlo più volte.
    """
    t = task_times
    best_load, best_set = -1, frozenset()
    seen: set[frozenset[int]] = set()
    stack = [(frozenset(), 0, dict(missing_preds), frozenset(available))]

    while stack and len(seen) < node_limit:
        chosen, load, missing, avail = stack.pop()
        if chosen in seen:
            continue
        seen.add(chosen)
        if load > best_load:
            best_load, best_set = load, chosen
            if load == capacity:                  # stazione satura: non si fa meglio
                break
        # Ordinamento crescente: con lo stack esce per prima l'operazione più
        # lunga, così i buoni riempimenti si trovano presto.
        for i in sorted(avail, key=lambda k: (t[k], -k)):
            if load + t[i] > capacity:
                continue
            new_missing = dict(missing)
            new_avail = set(avail)
            new_avail.remove(i)
            for j in successors[i]:
                new_missing[j] -= 1
                if new_missing[j] == 0:
                    new_avail.add(j)
            stack.append((chosen | {i}, load + t[i], new_missing, frozenset(new_avail)))

    # Il limite è scattato se si è usciti dal ciclo senza aver saturato la
    # stazione e resta almeno un insieme non ancora esplorato.
    limit_hit = (
        best_load < capacity
        and len(seen) >= node_limit
        and any(entry[0] not in seen for entry in stack)
    )
    return list(best_set), limit_hit


def _assign_with_cycle_time(
    instance: ALBInstance, graph: PrecedenceGraph, c: int, node_limit: int
) -> tuple[tuple[int, ...] | None, int]:
    """Stazione di ogni operazione se c basta con m stazioni, altrimenti None.

    Il secondo valore è il numero di stazioni in cui è scattato il limite di nodi.
    """
    n, m, t = instance.n_tasks, instance.m_stations, instance.task_times
    successors = [tuple(graph.successors(i)) for i in range(n)]
    missing = {i: len(graph.predecessors(i)) for i in range(n)}
    available = {i for i in range(n) if missing[i] == 0}
    stations = [0] * n
    hits = 0

    for s in range(1, m + 1):
        chosen, limit_hit = saturate_station(t, successors, missing, available, c, node_limit)
        hits += limit_hit
        for i in chosen:
            stations[i] = s
        # Si aggiornano i disponibili dopo aver segnato tutte le scelte: un'operazione
        # sbloccata e scelta nella stessa stazione non deve tornare disponibile.
        for i in chosen:
            available.discard(i)
            for j in successors[i]:
                missing[j] -= 1
                if missing[j] == 0 and stations[j] == 0:
                    available.add(j)
        if not available:
            break

    return (tuple(stations) if all(stations) else None), hits


def solve(
    instance: ALBInstance,
    graph: PrecedenceGraph | None = None,
    *,
    node_limit: int = 20_000,
) -> SolveResult:
    """Euristica di Hoffmann con ricerca del tempo ciclo dal lower bound."""
    t0 = time.perf_counter()
    graph = graph or PrecedenceGraph(instance)
    lb = lower_bound(instance, graph)

    # c = somma dei tempi funziona sempre (tutto in una stazione): il ciclo termina.
    hits_total = 0
    for c in range(lb, instance.total_time + 1):
        stations, hits = _assign_with_cycle_time(instance, graph, c, node_limit)
        hits_total += hits
        if stations is not None:
            break

    solution = Solution(instance, stations)
    if errs := violations(solution):
        raise RuntimeError(f"{instance.name}: soluzione non ammissibile: {errs[:5]}")

    objective = solution.max_load
    return SolveResult(
        method="hoffmann",
        instance_name=instance.name,
        status=Status.OPTIMAL if objective == lb else Status.FEASIBLE,
        objective=objective,
        lower_bound=lb,
        time_s=time.perf_counter() - t0,
        solution=solution,
        extra={
            "tried_cycle_times": c - lb + 1,
            "node_limit": node_limit,
            "node_limit_hits": hits,
            "node_limit_hits_total": hits_total,
        },
    )