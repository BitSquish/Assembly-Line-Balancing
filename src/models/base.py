"""Classe base per i modelli PLI del SALBP-2."""

from __future__ import annotations

import math
import time

import pulp

from ..solution import Solution, SolveResult, Status, violations


class PLIModel:
    """Parte comune ai modelli PLI: risoluzione con HiGHS e lettura dell'esito.
    
    Le sottoclassi devono definire `name`, `__init__` (impostando self.instance,
    self.c_min, self.c_max) e `build()` (che popola self.prob e self.x).
    """

    name: str

    def solve(self, time_limit: float, *, msg: bool = False) -> SolveResult:
        t0 = time.perf_counter()
        prob = self.prob if getattr(self, "prob", None) is not None else self.build()
        
        # MIPGapAbs < 1: l'ottimo è intero, quindi quando la distanza tra
        # soluzione e bound scende sotto 1 l'ottimo è dimostrato. Con la sola
        # tolleranza relativa di default (1e-4), su valori oltre 10 000 Gurobi
        # potrebbe fermarsi prima di averlo dimostrato.
        prob.solve(pulp.GUROBI(msg=msg, timeLimit=time_limit, MIPGapAbs=0.999))
        elapsed = time.perf_counter() - t0
        status, dual_bound = self._read_status(prob)

        elapsed = time.perf_counter() - t0

        solution = self._extract_solution() if status in (Status.OPTIMAL, Status.FEASIBLE) else None
        if solution is not None and (errs := violations(solution)):
            raise RuntimeError(f"{self.instance.name}: soluzione inammissibile: {errs[:5]}")

        lb = getattr(self, "c_min", 0)
        if dual_bound is not None and math.isfinite(dual_bound):
            lb = max(lb, math.ceil(dual_bound - 1e-6))
        
        objective = solution.max_load if solution else None
        
        # "Ottimo" solo se il bound lo dimostra davvero: vale per qualsiasi solver.
        if status is Status.OPTIMAL and objective is not None and objective > lb:
            status = Status.FEASIBLE

        return SolveResult(
            method=self.name,
            instance_name=self.instance.name,
            status=status,
            objective=objective,
            lower_bound=lb,
            time_s=elapsed,
            solution=solution,
            extra={
                "c_min": getattr(self, "c_min", None),
                "c_max": getattr(self, "c_max", None),
                "n_vars": prob.numVariables(),
                "n_constraints": prob.numConstraints(),
            },
        )
    
    def _read_status(self, prob: pulp.LpProblem) -> tuple[Status, float | None]:
        m = getattr(prob, "solverModel", None)   # il gurobipy.Model creato da PuLP
        if m is None:
            if prob.status == pulp.LpStatusOptimal: return Status.OPTIMAL, None
            if prob.status == pulp.LpStatusInfeasible: return Status.INFEASIBLE, None
            return Status.NO_SOLUTION, None

        import gurobipy
        from gurobipy import GRB

        try:
            bound = m.ObjBound                   # bound duale del branch and bound
        except (AttributeError, gurobipy.GurobiError):
            bound = None

        if m.Status == GRB.OPTIMAL:
            return Status.OPTIMAL, bound
        if m.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
            return Status.INFEASIBLE, None
        if m.Status == GRB.NUMERIC:
            return Status.SOLVER_ERROR, None
        if m.SolCount > 0:                       # time limit con incumbent
            return Status.FEASIBLE, bound
        return Status.NO_SOLUTION, bound

    def _extract_solution(self) -> Solution:
        stations = [0] * self.instance.n_tasks
        for (i, s), var in self.x.items():
            if (var.varValue or 0.0) > 0.5:
                stations[i] = s
        return Solution(self.instance, tuple(stations))

    def build(self) -> pulp.LpProblem:
        raise NotImplementedError(f"{type(self).__name__} deve definire build()")