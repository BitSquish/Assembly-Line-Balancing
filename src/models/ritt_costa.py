"""Modello PLI per il SALBP-2 con finestre di stazione dipendenti dal tempo ciclo.

Riferimento: Ritt & Costa (2018), "Improved integer programming models for simple assembly line balancing and related
problems", formulazione con variabili di tempo ciclo r_t e tagli dinamici sulle finestre di stazione.

Notazione (stazioni 1..m, task 0-based):
    C = {c_min, ..., c_max}            tempi ciclo candidati
    E_i(t), L_i(t)                     finestre di stazione (bounds.py)
    x[i, s] in {0,1}                   task i nella stazione s, solo per
                                       s in [E_i(c_max), L_i(c_max)]
    r[t] in {0,1}                      vale 1 se il tempo ciclo scelto è t
    c                                  tempo ciclo (carico massimo)

    min c
    (1) sum_{s} x[i, s] = 1                                   per ogni i
    (2) sum_{i} t_i x[i, s] <= c                              per ogni s
    (3) sum_{t} r[t] = 1,   c = sum_{t} t r[t]
    (4) sum_{s<=k} x[i, s] >= sum_{s<=k} x[j, s]              per ogni (i,j), k
    (5) sum_{u<=e} x[i, u] <= 1 - sum_{t: e < E_i(t)} r[t]
            per e in [E_i(c_max), E_i(c_min))
    (6) sum_{u>=l} x[i, u] <= 1 - sum_{t: L_i(t) < l} r[t]
            per l in (L_i(c_min), L_i(c_max)]

Le variabili x[i, s] fuori dalla finestra statica non vengono create: le
somme le omettono semplicemente.
"""


from __future__ import annotations

import pulp
from .base import PLIModel


class RittCostaModel(PLIModel):
    
    name = "ritt_costa"

    def __init__(self, instance, graph=None, *, upper_bound=None) -> None:
        super().__init__(instance, graph, upper_bound=upper_bound)
        self.r: dict[int, pulp.LpVariable] = {}

    def build(self) -> pulp.LpProblem:
        inst, sb = self.instance, self.sb
        n, m = inst.n_tasks, inst.m_stations
        c_min, c_max = self.c_min, self.c_max
        C = range(c_min, c_max + 1)

        E = [sb.earliest(i, c_max) for i in range(n)]
        L = [sb.latest(i, c_max) for i in range(n)]

        prob = pulp.LpProblem(f"{self.name}_{inst.name}", pulp.LpMinimize)

        x = {
            (i, s): pulp.LpVariable(f"x_{i}_{s}", cat=pulp.LpBinary)
            for i in range(n)
            for s in range(E[i], L[i] + 1)
        }
        r = {t: pulp.LpVariable(f"r_{t}", cat=pulp.LpBinary) for t in C}
        c = pulp.LpVariable("c", lowBound=c_min, upBound=c_max)

        prob += c, "tempo_ciclo"

        for i in range(n):
            prob += pulp.lpSum(x[i, s] for s in range(E[i], L[i] + 1)) == 1, f"assign_{i}"

        for s in range(1, m + 1):
            prob += (
                pulp.lpSum(inst.task_times[i] * x[i, s] for i in range(n) if E[i] <= s <= L[i])
                <= c,
                f"cap_{s}",
            )

        prob += pulp.lpSum(r.values()) == 1, "one_cycle"
        prob += c == pulp.lpSum(t * r[t] for t in C), "cycle_value"

        for i, j in self.graph.reduction:
            for k in range(E[j], L[i]):
                prob += (
                    pulp.lpSum(x[i, s] for s in range(E[i], k + 1))
                    >= pulp.lpSum(x[j, s] for s in range(E[j], k + 1)),
                    f"prec_{i}_{j}_{k}",
                )

        for i in range(n):
            for e in range(E[i], sb.earliest(i, c_min)):
                pushed = [r[t] for t in C if e < sb.earliest(i, t)]
                if pushed:
                    prob += (
                        pulp.lpSum(x[i, u] for u in range(E[i], e + 1)) <= 1 - pulp.lpSum(pushed),
                        f"early_{i}_{e}",
                    )
            for l in range(sb.latest(i, c_min) + 1, L[i] + 1):
                pushed = [r[t] for t in C if sb.latest(i, t) < l]
                if pushed:
                    prob += (
                        pulp.lpSum(x[i, u] for u in range(l, L[i] + 1)) <= 1 - pulp.lpSum(pushed),
                        f"late_{i}_{l}",
                    )

        self.prob, self.x, self.r, self.c = prob, x, r, c
        return prob