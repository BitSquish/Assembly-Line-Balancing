"""Riesecuzione dopo il cambio di lower bound, e verifica.

Uso:
    python -m scripts.rerun_bound prepare [--extra ISTANZA:METODO ...]
    python -m scripts.run_experiments --manifest instances/manifest.csv \\
        --out results/results.csv --time-limit 180
    python -m scripts.rerun_bound check [--sample 5]

La campagna è stata eseguita con il bound a finestre semplici
(window_lower_bound); il codice attuale usa lower_bound, che aggiunge teste e code
ricorsive. Il bound entra nei metodi solo come valore: c_min dei modelli PLI e
punto di partenza della ricerca del tempo ciclo nelle euristiche. Quindi:
  - le euristiche si rieseguono tutte, perché il loro tempo include il calcolo
    del bound (le soluzioni devono restare identiche);
  - i PLI si rieseguono solo nelle istanze in cui il valore del bound cambia:
    nelle altre il modello è identico.

prepare: copia results.csv in results/results_bound_semplice.csv, scrive in
results/bound_cambiato.csv le istanze in cui il bound cambia e toglie da
results.csv le righe da rifare. run_experiments salta le righe presenti,
quindi riesegue solo quelle tolte. --extra aggiunge singole esecuzioni da
rifare (per esempio una riga anomala).

check: confronta i nuovi risultati con la copia. Le soluzioni delle euristiche
devono coincidere; nei PLI rieseguiti, se entrambe le esecuzioni dimostrano
l'ottimo, il valore deve coincidere. Con --sample k riesegue anche k PLI su
istanze in cui il bound non cambia, e controlla che il risultato coincida.
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path

from src.bounds import lower_bound, window_lower_bound
from src.graph import PrecedenceGraph
from src.instance import ALBInstance

MANIFEST = Path("instances/manifest.csv")
RESULTS = Path("results/results.csv")
BACKUP = Path("results/storico/results_bound_semplice.csv")
CHANGED = Path("results/storico/bound_cambiato.csv")


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames), list(reader)


def num(value: str) -> float | None:
    return float(value) if value not in (None, "") else None


def prepare(extra: list[str]) -> None:
    if BACKUP.exists():
        raise SystemExit(f"{BACKUP} esiste già: prepare è già stato eseguito.")
    shutil.copyfile(RESULTS, BACKUP)
    print(f"Copia dei risultati originali: {BACKUP}")

    _, manifest = read_csv(MANIFEST)
    changed = []
    for k, r in enumerate(manifest, 1):
        inst = ALBInstance.load(r["path"], name=r["instance"])
        graph = PrecedenceGraph(inst)
        old = window_lower_bound(inst, graph)        
        new = lower_bound(inst, graph)
        if new != old:
            changed.append({"instance": r["instance"], "group": r["group"],
                            "bound_semplice": old, "bound_ricorsivo": new})
        print(f"\rCalcolo dei bound: {k}/{len(manifest)}", end="", flush=True)
    print()

    with CHANGED.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["instance", "group",
                                                "bound_semplice", "bound_ricorsivo"])
        writer.writeheader()
        writer.writerows(changed)
    print(f"Istanze con bound diverso: {len(changed)} (elenco in {CHANGED})")

    names = {c["instance"] for c in changed}
    extra_keys = {tuple(e.split(":", 1)) for e in extra}
    fields, rows = read_csv(BACKUP)
    keep = [r for r in rows
            if r["kind"] == "pli"
            and r["instance"] not in names
            and (r["instance"], r["method"]) not in extra_keys]
    with RESULTS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(keep)

    removed = len(rows) - len(keep)
    heur = sum(r["kind"] != "pli" for r in rows)
    print(f"Righe tolte da {RESULTS}: {removed} "
          f"({heur} euristiche, {removed - heur} PLI). Ora lancia run_experiments.")


def check(sample: int) -> None:
    _, old_rows = read_csv(BACKUP)
    _, new_rows = read_csv(RESULTS)
    _, changed_rows = read_csv(CHANGED)
    old = {(r["instance"], r["method"]): r for r in old_rows}
    new = {(r["instance"], r["method"]): r for r in new_rows}
    changed = {r["instance"] for r in changed_rows}

    missing = set(old) - set(new)
    if missing:
        print(f"Mancano {len(missing)} esecuzioni: rilancia run_experiments e poi check.")
        return

    problems = []
    proven = {}
    for key, n in new.items():
        o = old[key]
        method = key[1]
        before, after = proven.get(method, (0, 0))
        proven[method] = (before + (o["status"] == "optimal"),
                          after + (n["status"] == "optimal"))
        if n["status"] == "error":
            problems.append(f"{key}: errore {n['error']}")
        elif n["kind"] != "pli":
            if num(n["objective"]) != num(o["objective"]):
                problems.append(f"{key}: soluzione euristica cambiata "
                                f"{o['objective']} -> {n['objective']}")
        elif key[0] in changed and o["status"] == n["status"] == "optimal":
            if num(n["objective"]) != num(o["objective"]):
                problems.append(f"{key}: ottimo diverso {o['objective']} -> {n['objective']}")

    print("Ottimi dimostrati (prima -> dopo):")
    for method, (before, after) in proven.items():
        print(f"  {method:20s} {before:4d} -> {after:4d}")

    if sample:
        from scripts.run_experiments import METHODS
        _, manifest = read_csv(MANIFEST)
        paths = {r["instance"]: r["path"] for r in manifest}
        candidates = sorted(
            key for key, o in old.items()
            if o["kind"] == "pli" and o["status"] == "optimal"
            and key[0] not in changed and (num(o["time_s"]) or 0) < 10
        )
        for name, method in random.Random(0).sample(candidates, min(sample, len(candidates))):
            inst = ALBInstance.load(paths[name], name=name)
            res = METHODS[method][1](inst, 180.0)
            o = old[(name, method)]
            same = res.status.value == "optimal" and res.objective == num(o["objective"])
            print(f"  controllo {name} {method}: prima {o['objective']}, "
                  f"ora {res.objective} ({res.status.value}) -> {'ok' if same else 'DIVERSO'}")
            if not same:
                problems.append(f"{(name, method)}: rieseguito senza cambio di bound, risultato diverso")

    if problems:
        print(f"\nProblemi: {len(problems)}")
        for p in problems[:20]:
            print(f"  {p}")
    else:
        print("\nNessun problema: le soluzioni coincidono dove devono coincidere.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--extra", nargs="*", default=[], metavar="ISTANZA:METODO")
    c = sub.add_parser("check")
    c.add_argument("--sample", type=int, default=0)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.extra)
    else:
        check(args.sample)


if __name__ == "__main__":
    main()