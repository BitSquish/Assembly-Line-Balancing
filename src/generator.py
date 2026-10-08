"""Generazione pseudo-casuale di istanze SALBP-2 con order strength controllata.

Ogni istanza è definita da:
    n                numero di operazioni;
    m                numero di stazioni;
    order_strength   densità del grafo delle precedenze (OS, vedi graph.py);
    time_dist        distribuzione dei tempi ("uniform" o "bimodal");
    seed             seme del generatore casuale: stessi parametri e stesso
                     seme danno la stessa istanza.

Grafo delle precedenze. L'OS è la frazione di coppie di operazioni il cui
ordine è fissato dalle precedenze, dirette o indirette: dipende dalla chiusura
transitiva, quindi scegliere una probabilità per ogni arco non la controlla
bene. Il generatore la controlla direttamente:
    - le operazioni sono numerate in ordine topologico e ogni arco va da
      un'operazione a una di indice maggiore (u < v), così il grafo è
      aciclico per costruzione;
    - si aggiungono archi casuali uno alla volta, scartando quelli già
      implicati da altri (non cambiano l'ordine rappresentato);
    - ci si ferma appena l'OS raggiunge l'obiettivo. Un arco che la farebbe
      superare di oltre la tolleranza viene scartato e se ne prova un altro.
L'OS ottenuta viene salvata nei metadati accanto a quella obiettivo.

Tempi (interi, tra t_min e t_max):
    - "uniform": uniformi su [t_min, t_max];
    - "bimodal": con probabilità 0,8 un tempo "corto" nel primo terzo
      dell'intervallo, altrimenti un tempo "lungo" nell'ultimo terzo. Molte
      operazioni corte e poche lunghe rendono più difficile bilanciare.

Il passo che porta l'OS al valore obiettivo, aggiungendo archi casuali uno
alla volta, è lo stesso di SALBPGen: Otto, A., Otto, C., & Scholl, A. (2013).
Systematic data generation and test design for solution algorithms on the
example of SALBPGen for assembly line balancing. European Journal of
Operational Research, 228(1). A differenza di SALBPGen non si costruisce prima
il grafo a stadi e non si controllano catene e colli di bottiglia. Le
distribuzioni dei tempi sono una scelta del progetto.
"""

from __future__ import annotations

import random

from .instance import ALBInstance

TIME_DISTRIBUTIONS = ("uniform", "bimodal")


def _task_times(
    rng: random.Random, n: int, dist: str, t_min: int, t_max: int
) -> list[int]:
    if dist == "uniform":
        return [rng.randint(t_min, t_max) for _ in range(n)]
    if dist == "bimodal":
        third = max(1, (t_max - t_min + 1) // 3)
        short = (t_min, t_min + third - 1)
        long_ = (t_max - third + 1, t_max)
        return [
            rng.randint(*short) if rng.random() < 0.8 else rng.randint(*long_)
            for _ in range(n)
        ]
    raise ValueError(f"distribuzione dei tempi sconosciuta: {dist!r} ({TIME_DISTRIBUTIONS})")


def _precedences(
    rng: random.Random, n: int, target_os: float, tolerance: float, max_attempts: int
) -> tuple[list[tuple[int, int]], float]:
    """Archi (u, v) con u < v fino a raggiungere l'OS obiettivo.

    La chiusura transitiva si aggiorna a ogni arco in modo incrementale, con
    maschere di bit: desc[u] sono i discendenti di u, anc[v] i suoi antenati.
    """
    max_pairs = n * (n - 1) // 2
    if max_pairs == 0 or target_os <= 0:
        return [], 0.0

    desc = [0] * n
    anc = [0] * n
    closure_pairs = 0
    arcs: list[tuple[int, int]] = []

    def os_value() -> float:
        return closure_pairs / max_pairs

    attempts = 0
    while os_value() < target_os and attempts < max_attempts:
        attempts += 1
        u, v = sorted(rng.sample(range(n), 2))
        if desc[u] >> v & 1:                 # arco già implicato: non cambia nulla
            continue

        # Coppie nuove: ogni antenato di u (u compreso) raggiunge ora v e i
        # discendenti di v che non raggiungeva già.
        sources = anc[u] | (1 << u)
        targets = desc[v] | (1 << v)
        new_pairs = sum(
            bin(targets & ~desc[a]).count("1")
            for a in range(n) if sources >> a & 1
        )
        if (closure_pairs + new_pairs) / max_pairs > target_os + tolerance:
            continue                         # supererebbe troppo l'obiettivo

        for a in range(n):
            if sources >> a & 1:
                desc[a] |= targets
        for d in range(n):
            if targets >> d & 1:
                anc[d] |= sources
        closure_pairs += new_pairs
        arcs.append((u, v))

    return arcs, os_value()


def generate(
    n: int,
    m: int,
    order_strength: float,
    *,
    time_dist: str = "uniform",
    t_min: int = 1,
    t_max: int = 100,
    seed: int = 0,
    name: str | None = None,
    tolerance: float = 0.02,
    max_attempts: int = 200_000,
) -> ALBInstance:
    """Genera un'istanza. Stessi argomenti e stesso seed danno la stessa istanza."""
    if not 1 <= m <= n:
        raise ValueError(f"serve 1 <= m <= n (m={m}, n={n})")
    if not 0 <= order_strength <= 1:
        raise ValueError(f"order_strength deve stare in [0, 1] (è {order_strength})")
    if not 1 <= t_min <= t_max:
        raise ValueError(f"serve 1 <= t_min <= t_max (t_min={t_min}, t_max={t_max})")

    rng = random.Random(seed)
    times = _task_times(rng, n, time_dist, t_min, t_max)
    arcs, achieved = _precedences(rng, n, order_strength, tolerance, max_attempts)

    return ALBInstance(
        name=name or f"n{n}_m{m}_os{order_strength:g}_{time_dist}_s{seed}",
        task_times=tuple(times),
        precedences=tuple(arcs),
        m_stations=m,
        meta={
            "generator": "src.generator.generate",
            "seed": seed,
            "order_strength_target": order_strength,
            "order_strength": achieved,
            "time_dist": time_dist,
            "t_min": t_min,
            "t_max": t_max,
        },
    )