"""Esegue la campagna di esperimenti: due modelli PLI e due euristiche su ogni istanza.

Uso:

    # campagna completa
    python -m scripts.run_experiments --manifest instances/manifest.csv \\
        --out results/results.csv --time-limit 180

    # solo alcuni metodi
    python -m scripts.run_experiments ... --methods hoffmann gruppi

Per ogni istanza del manifest (scritto da gen_instances.py) e per ogni metodo
scrive una riga nel CSV di output, appena il risultato è pronto. Se il CSV esiste
già, le coppie (istanza, metodo) presenti vengono saltate: dopo un'interruzione
basta rilanciare lo stesso comando e la campagna riprende da dove era rimasta.

I modelli PLI ricevono solo l'istanza e il time limit: nessun upper bound viene
passato dalle euristiche, così PLI ed euristiche restano indipendenti e il
confronto euristica / (ottimo o lower bound del PLI) è pulito.

Se un metodo solleva un'eccezione (per esempio il modello supera i limiti della
licenza Gurobi) la riga viene scritta con stato "error" e il messaggio, e la
campagna prosegue con il metodo successivo.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import time
import traceback
from pathlib import Path

from src.heuristic import groups, hoffmann
from src.instance import ALBInstance
from src.models import PattersonAlbrachtModel, RittCostaModel

# nome nel CSV -> (tipo, funzione che risolve l'istanza)
METHODS = {
    "patterson_albracht": ("pli", lambda inst, tl: _solve_pli(PattersonAlbrachtModel, inst, tl)),
    "ritt_costa": ("pli", lambda inst, tl: _solve_pli(RittCostaModel, inst, tl)),
    "hoffmann": ("euristica", lambda inst, tl: hoffmann.solve(inst)),
    "gruppi": ("euristica", lambda inst, tl: groups.solve(inst)),
}

FIELDS = [
    "instance", "group", "n", "m", "os", "tasks_per_station", "time_dist",
    "method", "kind", "status", "objective", "lower_bound", "gap",
    "time_s", "build_s", "n_vars", "n_constraints", "extra", "error",
]


def _solve_pli(model_class, inst: ALBInstance, time_limit: float):
    model = model_class(inst)
    try:
        return model.solve(time_limit=time_limit)
    finally:
        # Libera subito la memoria del modello Gurobi: su centinaia di istanze
        # gli oggetti non rilasciati si accumulerebbero.
        grb = getattr(getattr(model, "prob", None), "solverModel", None)
        if grb is not None and hasattr(grb, "dispose"):
            grb.dispose()
        del model
        gc.collect()


def _already_done(out: Path) -> set[tuple[str, str]]:
    if not out.exists():
        return set()
    with out.open(newline="", encoding="utf-8") as fh:
        return {(row["instance"], row["method"]) for row in csv.DictReader(fh)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=180.0,
                    help="secondi per ogni modello PLI (default 180)")
    parser.add_argument("--methods", nargs="+", choices=list(METHODS), default=list(METHODS))
    args = parser.parse_args()

    with args.manifest.open(newline="", encoding="utf-8") as fh:
        instances = list(csv.DictReader(fh))

    done = _already_done(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not args.out.exists()
    total = len(instances) * len(args.methods)
    print(f"{len(instances)} istanze x {len(args.methods)} metodi = {total} esecuzioni "
          f"({len(done)} già presenti in {args.out})")

    with args.out.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()

        count = 0
        for row in instances:
            inst = ALBInstance.load(row["path"], name=row["instance"])
            for method in args.methods:
                count += 1
                if (row["instance"], method) in done:
                    continue
                kind, solve = METHODS[method]
                out = {
                    "instance": row["instance"], "group": row["group"],
                    "n": row["n"], "m": row["m"], "os": row["os"],
                    "tasks_per_station": row["tasks_per_station"],
                    "time_dist": row["time_dist"], "method": method, "kind": kind,
                }
                t0 = time.perf_counter()
                try:
                    res = solve(inst, args.time_limit)
                    extra = dict(res.extra)
                    out.update({
                        "status": res.status.value,
                        "objective": res.objective,
                        "lower_bound": res.lower_bound,
                        "gap": None if res.gap is None else round(res.gap, 6),
                        "time_s": round(res.time_s, 3),
                        "build_s": round(extra.pop("build_s", 0.0), 3) if kind == "pli" else "",
                        "n_vars": extra.pop("n_vars", ""),
                        "n_constraints": extra.pop("n_constraints", ""),
                        "extra": json.dumps(extra),
                        "error": "",
                    })
                except Exception as exc:                       # noqa: BLE001
                    out.update({
                        "status": "error",
                        "time_s": round(time.perf_counter() - t0, 3),
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    traceback.print_exc()
                writer.writerow(out)
                fh.flush()                                     # riga su disco subito
                print(f"[{count}/{total}] {row['instance']:28s} {method:18s} "
                      f"{out['status']:12s} obj={out.get('objective')} "
                      f"lb={out.get('lower_bound')} t={out['time_s']}s")


if __name__ == "__main__":
    main()