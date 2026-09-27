import random
from itertools import product
from src.instance import ALBInstance

def brute_force_optimum(inst: ALBInstance) -> int:
    best = None
    for stations in product(range(1, inst.m_stations + 1), repeat=inst.n_tasks):
        if any(stations[u] > stations[v] for u, v in inst.precedences):
            continue
        loads = [0] * inst.m_stations
        for i, s in enumerate(stations):
            loads[s - 1] += inst.task_times[i]
        value = max(loads)
        if best is None or value < best:
            best = value
    return best

def random_instance(seed: int, n: int = 7, m: int = 3, p: float = 0.3) -> ALBInstance:
    rng = random.Random(seed)
    times = [rng.randint(1, 10) for _ in range(n)]
    prec = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    return ALBInstance(f"rnd{seed}", times, prec, m_stations=m)