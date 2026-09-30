"""Modello PLI per il SALBP-2 con le precedenze di Bowman (1960) e White (1961).

Riferimenti:
    Bowman, E. H. (1960). Assembly-line balancing by linear programming.
        Operations Research, 8(3), 385-389.
    White, W. W. (1961). Comments on a paper by Bowman.
        Operations Research, 9(2), 274-276.
    Formulazione BW come riportata in Ritt & Costa (2018), eq. (2)-(4), (9)-(10).

Notazione (stazioni 1..m, task 0-based):
    x[i, s] in {0,1}   task i nella stazione s, solo per s in [E_i(c_max), L_i(c_max)]
    c                  tempo ciclo (carico massimo)

    min c
    (1) sum_s x[i, s] = 1                               per ogni task i
    (2) sum_i t_i x[i, s] <= c                          per ogni stazione s
    (3) x[j, t] <= sum_{s <= t} x[i, s]                 per ogni arco (i, j) e stazione t

Il vincolo (3) dice: se j sta nella stazione t, i sta in t o in una stazione
precedente. È la precedenza di Ritt & Costa con un solo termine a sinistra
invece della somma cumulativa: per questo il suo rilassamento è più debole.
"""

from __future__ import annotations

import pulp

from ..bounds import StationBounds, greedy_solution, lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from .base import PLIModel


class BowmanWhiteModel(PLIModel):

    name = "bowman_white"

    def __init__(
        self,
        instance: ALBInstance,
        graph: PrecedenceGraph | None = None,
        *,
        upper_bound: int | None = None,
    ) -> None:
        self.instance = instance
        self.graph = graph or PrecedenceGraph(instance)
        self.sb = StationBounds.from_graph(self.graph)

        ub = greedy_solution(instance, self.graph).max_load
        if upper_bound is not None:
            ub = min(ub, upper_bound)
        self.c_max = ub
        self.c_min = lower_bound(instance, self.graph, upper_bound=ub)

        self.prob: pulp.LpProblem | None = None
        self.x: dict[tuple[int, int], pulp.LpVariable] = {}
        self.c: pulp.LpVariable | None = None

    def build(self) -> pulp.LpProblem:
        inst, sb = self.instance, self.sb
        n, m = inst.n_tasks, inst.m_stations

        # Finestre statiche: il confronto misura
        # la precedenza e i tagli, non il pre-processing.
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

        # (3) precedenze di Bowman-White. Se t < E_i la somma a destra è vuota
        # e il vincolo impone x[j, t] = 0: j non può stare prima che i possa iniziare.
        for i, j in self.graph.reduction:
            for t in range(E[j], L[j] + 1):
                prob += (
                    x[j, t] <= pulp.lpSum(x[i, s] for s in range(E[i], min(t, L[i]) + 1)),
                    f"prec_{i}_{j}_{t}",
                )

        self.prob, self.x, self.c = prob, x, c
        return prob