"""Modello PLI di riferimento, senza finestre di stazione.

Crea x[i, s] per ogni task e ogni stazione, e impone le precedenze sul numero
di stazione: sum_s s*x[i,s] <= sum_s s*x[j,s]. Del pre-processing usa solo i
bound su c (lower bound combinatorio, soluzione greedy) e la riduzione
transitiva degli archi, gli stessi di RittCostaModel: il confronto misura
quindi l'effetto delle finestre e dei tagli.
"""

from __future__ import annotations

import pulp

from ..bounds import greedy_solution, simple_lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from .base import PLIModel


class NaiveModel(PLIModel):
    
    name = "naive"

    def __init__(
        self,
        instance: ALBInstance,
        graph: PrecedenceGraph | None = None,
        *,
        upper_bound: int | None = None,
    ) -> None:
        self.instance = instance
        self.graph = graph or PrecedenceGraph(instance)

        ub = greedy_solution(instance, self.graph).max_load
        if upper_bound is not None:
            ub = min(ub, upper_bound)
        self.c_max = ub
        self.c_min = simple_lower_bound(instance)

        self.prob: pulp.LpProblem | None = None
        self.x: dict[tuple[int, int], pulp.LpVariable] = {}
        self.c: pulp.LpVariable | None = None

    def build(self) -> pulp.LpProblem:
        inst = self.instance
        n, m = inst.n_tasks, inst.m_stations

        prob = pulp.LpProblem(f"{self.name}_{inst.name}", pulp.LpMinimize)

        x = {
            (i, s): pulp.LpVariable(f"x_{i}_{s}", cat=pulp.LpBinary)
            for i in range(n)
            for s in range(1, m + 1)
        }
        c = pulp.LpVariable("c", lowBound=self.c_min, upBound=self.c_max)

        prob += c, "tempo_ciclo"

        for i in range(n):
            prob += pulp.lpSum(x[i, s] for s in range(1, m + 1)) == 1, f"assign_{i}"

        for s in range(1, m + 1):
            prob += pulp.lpSum(inst.task_times[i] * x[i, s] for i in range(n)) <= c, f"cap_{s}"

        for i, j in self.graph.reduction:
            prob += (
                pulp.lpSum(s * x[i, s] for s in range(1, m + 1))
                <= pulp.lpSum(s * x[j, s] for s in range(1, m + 1)),
                f"prec_{i}_{j}",
            )

        self.prob, self.x, self.c = prob, x, c
        return prob