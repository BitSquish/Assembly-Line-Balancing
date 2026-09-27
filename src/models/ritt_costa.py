"""Modello PLI per il SALBP-2 con finestre di stazione dipendenti dal tempo ciclo.

Riferimento: Ritt & Costa, "Improved integer programming models for simple assembly line balancing and related
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

import math
import time

import pulp

from ..bounds import StationBounds, greedy_solution, lower_bound
from ..graph import PrecedenceGraph
from ..instance import ALBInstance
from ..solution import Solution, SolveResult, Status, violations


class RittCostaModel:
    """Costruzione e risoluzione del modello su una singola istanza."""

    name = "ritt_costa"

    def __init__(
        self,
        instance: ALBInstance,
        graph: PrecedenceGraph | None = None,
        *,
        upper_bound: int | None = None,
    ) -> None:
        """
        Args:
            upper_bound: carico massimo di una soluzione ammissibile nota, per
                esempio quella dell'euristica. Più è basso, più strette sono le
                finestre e più piccolo è il modello. Se manca si usa la
                soluzione greedy di bounds.py.
        """
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
        self.r: dict[int, pulp.LpVariable] = {}
        self.c: pulp.LpVariable | None = None

    # ------------------------------------------------------------------ build

    def build(self) -> pulp.LpProblem:
        inst, sb = self.instance, self.sb
        n, m = inst.n_tasks, inst.m_stations
        c_min, c_max = self.c_min, self.c_max
        C = range(c_min, c_max + 1)

        # Finestra statica: la più larga, quella del tempo ciclo massimo.
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

        # (1) assegnamento unico
        for i in range(n):
            prob += (
                pulp.lpSum(x[i, s] for s in range(E[i], L[i] + 1)) == 1,
                f"assign_{i}",
            )

        # (2) capacità delle stazioni
        for s in range(1, m + 1):
            prob += (
                pulp.lpSum(
                    inst.task_times[i] * x[i, s] for i in range(n) if E[i] <= s <= L[i]
                )
                <= c,
                f"cap_{s}",
            )

        # (3) scelta del tempo ciclo
        prob += pulp.lpSum(r.values()) == 1, "one_cycle"
        prob += c == pulp.lpSum(t * r[t] for t in C), "cycle_value"

        # (4) precedenze cumulative, solo sugli archi della riduzione
        # transitiva (le altre precedenze ne seguono) e solo per i k in cui il
        # vincolo non è banale: per k < E_j il membro destro è 0, per k >= L_i
        # il sinistro è 1.
        for i, j in self.graph.reduction:
            for k in range(E[j], L[i]):
                prob += (
                    pulp.lpSum(x[i, s] for s in range(E[i], k + 1))
                    >= pulp.lpSum(x[j, s] for s in range(E[j], k + 1)),
                    f"prec_{i}_{j}_{k}",
                )

        for i in range(n):
            # (5) tagli per anticipo: se il tempo ciclo scelto t ha E_i(t) > e,
            # il task i non può stare in una stazione <= e.
            for e in range(E[i], sb.earliest(i, c_min)):
                pushed = [r[t] for t in C if e < sb.earliest(i, t)]
                if pushed:
                    prob += (
                        pulp.lpSum(x[i, u] for u in range(E[i], e + 1))
                        <= 1 - pulp.lpSum(pushed),
                        f"early_{i}_{e}",
                    )
            # (6) tagli per ritardo: se il tempo ciclo scelto t ha L_i(t) < l,
            # il task i non può stare in una stazione >= l.
            for l in range(sb.latest(i, c_min) + 1, L[i] + 1):
                pushed = [r[t] for t in C if sb.latest(i, t) < l]
                if pushed:
                    prob += (
                        pulp.lpSum(x[i, u] for u in range(l, L[i] + 1))
                        <= 1 - pulp.lpSum(pushed),
                        f"late_{i}_{l}",
                    )

        self.prob, self.x, self.r, self.c = prob, x, r, c
        return prob

    # ------------------------------------------------------------------ solve

    def solve(self, time_limit: float, *, msg: bool = False) -> SolveResult:
        """Risolve con HiGHS entro time_limit secondi e restituisce l'esito.

        Il tempo misurato comprende la costruzione del modello: è il tempo
        che serve davvero per ottenere la risposta.
        """
        t0 = time.perf_counter()
        prob = self.prob or self.build()
        prob.solve(pulp.HiGHS(msg=msg, timeLimit=time_limit))
        elapsed = time.perf_counter() - t0

        status, dual_bound = self._read_status(prob)

        solution = self._extract_solution() if status in (Status.OPTIMAL, Status.FEASIBLE) else None
        if solution is not None and (errs := violations(solution)):
            raise RuntimeError(f"{self.instance.name}: soluzione PLI non ammissibile: {errs[:5]}")

        # c è intero, quindi il bound del solver si può arrotondare per eccesso.
        lb = self.c_min
        if dual_bound is not None and math.isfinite(dual_bound):
            lb = max(lb, math.ceil(dual_bound - 1e-6))
        objective = solution.max_load if solution else None
        if status is Status.OPTIMAL and objective is not None:
            lb = objective

        return SolveResult(
            method=self.name,
            instance_name=self.instance.name,
            status=status,
            objective=objective,
            lower_bound=lb,
            time_s=elapsed,
            solution=solution,
            extra={
                "c_min": self.c_min,
                "c_max": self.c_max,
                "n_vars": prob.numVariables(),
                "n_constraints": prob.numConstraints(),
            },
        )

    def _read_status(self, prob: pulp.LpProblem) -> tuple[Status, float | None]:
        """Stato e bound duale letti direttamente da HiGHS.

        PuLP riduce tutto a pochi codici e non espone il bound duale del
        branch and bound, che al time limit è esattamente il dato richiesto.
        Il solver pulp.HiGHS lascia l'oggetto highspy in prob.solverModel.
        """
        h = getattr(prob, "solverModel", None)
        if h is None:  # ripiego: solo lo stato di PuLP, senza bound duale
            if prob.status == pulp.LpStatusOptimal:
                return Status.OPTIMAL, None
            if prob.status == pulp.LpStatusInfeasible:
                return Status.INFEASIBLE, None
            return Status.NO_SOLUTION, None

        import highspy

        model_status = h.getModelStatus()
        info = h.getInfo()
        has_solution = info.primal_solution_status == 2  # kSolutionStatusFeasible
        if model_status == highspy.HighsModelStatus.kOptimal:
            status = Status.OPTIMAL
        elif model_status == highspy.HighsModelStatus.kInfeasible:
            status = Status.INFEASIBLE
        elif has_solution:
            status = Status.FEASIBLE
        else:
            status = Status.NO_SOLUTION
        return status, info.mip_dual_bound

    def _extract_solution(self) -> Solution:
        stations = [0] * self.instance.n_tasks
        for (i, s), var in self.x.items():
            if (var.varValue or 0.0) > 0.5:
                stations[i] = s
        return Solution(self.instance, tuple(stations))