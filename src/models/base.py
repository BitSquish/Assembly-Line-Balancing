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
        """Risolve con HiGHS entro time_limit secondi e restituisce l'esito."""
        t0 = time.perf_counter()
        prob = getattr(self, "prob", None) or self.build()
        prob.solve(pulp.HiGHS(msg=msg, timeLimit=time_limit))
        elapsed = time.perf_counter() - t0

        status, dual_bound = self._read_status(prob)

        solution = self._extract_solution() if status in (Status.OPTIMAL, Status.FEASIBLE) else None
        if solution is not None and (errs := violations(solution)):
            raise RuntimeError(f"{self.instance.name}: soluzione PLI non ammissibile: {errs[:5]}")

        lb = getattr(self, "c_min", 0)
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
                "c_min": getattr(self, "c_min", None),
                "c_max": getattr(self, "c_max", None),
                "n_vars": prob.numVariables(),
                "n_constraints": prob.numConstraints(),
            },
        )

    def _read_status(self, prob: pulp.LpProblem) -> tuple[Status, float | None]:
        h = getattr(prob, "solverModel", None)
        if h is None:
            if prob.status == pulp.LpStatusOptimal: return Status.OPTIMAL, None
            if prob.status == pulp.LpStatusInfeasible: return Status.INFEASIBLE, None
            return Status.NO_SOLUTION, None

        import highspy
        model_status = h.getModelStatus()
        info = h.getInfo()
        has_solution = info.primal_solution_status == 2
        
        if model_status == highspy.HighsModelStatus.kOptimal:
            return Status.OPTIMAL, info.mip_dual_bound
        elif model_status == highspy.HighsModelStatus.kInfeasible:
            return Status.INFEASIBLE, info.mip_dual_bound
        elif has_solution:
            return Status.FEASIBLE, info.mip_dual_bound
        return Status.NO_SOLUTION, info.mip_dual_bound

    def _extract_solution(self) -> Solution:
        stations = [0] * self.instance.n_tasks
        for (i, s), var in self.x.items():
            if (var.varValue or 0.0) > 0.5:
                stations[i] = s
        return Solution(self.instance, tuple(stations))