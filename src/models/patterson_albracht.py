"""Modello PLI per il SALBP-2 con le precedenze di Patterson & Albracht (1975).

Riferimenti:
    Patterson, J. H., & Albracht, J. J. (1975). Assembly-line balancing:
        zero-one programming with Fibonacci search. Operations Research,
        23(1), 166-172.
    Formulazione PA come riportata in Ritt & Costa (2018), eq. (21).

Notazione (stazioni 1..m, task 0-based):
    x[i, s] in {0,1}   task i nella stazione s, solo per s in [E_i(c_max), L_i(c_max)]
    c                  tempo ciclo (carico massimo)

    min c
    (1) sum_s x[i, s] = 1                               per ogni task i
    (2) sum_i t_i x[i, s] <= c                          per ogni stazione s
    (3) sum_s s * x[i, s] <= sum_s s * x[j, s]          per ogni arco (i, j)

Il vincolo (3) confronta direttamente il numero di stazione di i e di j: un
solo vincolo per arco, contro gli m per arco di Bowman-White e Ritt & Costa.
Modello più compatto, rilassamento più debole.
"""

from __future__ import annotations

import pulp
from .base import PLIModel


class PattersonAlbrachtModel(PLIModel):

    name = "patterson_albracht"

    def build(self) -> pulp.LpProblem:
        inst, sb = self.instance, self.sb
        n, m = inst.n_tasks, inst.m_stations

        # Finestre statiche, le stesse degli altri modelli: il confronto misura
        # la formulazione delle precedenze, non il pre-processing.
        E = [sb.earliest(i, self.c_max) for i in range(n)]
        L = [sb.latest(i, self.c_max) for i in range(n)]

        prob = pulp.LpProblem(f"{self.name}_{inst.name}", pulp.LpMinimize)

        x = {
            (i, s): pulp.LpVariable(f"x_{i}_{s}", cat=pulp.LpBinary)
            for i in range(n)
            for s in range(E[i], L[i] + 1)
        }
        c = pulp.LpVariable("c", lowBound=self.c_min, upBound=self.c_max)

        prob += c, "tempo_ciclo"

        # (1) assegnamento unico
        for i in range(n):
            prob += pulp.lpSum(x[i, s] for s in range(E[i], L[i] + 1)) == 1, f"assign_{i}"

        # (2) capacità delle stazioni
        for s in range(1, m + 1):
            prob += (
                pulp.lpSum(inst.task_times[i] * x[i, s] for i in range(n) if E[i] <= s <= L[i])
                <= c,
                f"cap_{s}",
            )

        # (3) precedenze di Patterson & Albracht: stazione di i <= stazione di j
        for i, j in self.graph.reduction:
            prob += (
                pulp.lpSum(s * x[i, s] for s in range(E[i], L[i] + 1))
                <= pulp.lpSum(s * x[j, s] for s in range(E[j], L[j] + 1)),
                f"prec_{i}_{j}",
            )

        self.prob, self.x, self.c = prob, x, c
        return prob