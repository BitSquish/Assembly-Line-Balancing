"""Genera le istanze del disegno sperimentale.

Uso:
    python -m scripts.gen_instances --config configs/design.json --out instances/

Per ogni gruppo (combinazione dei fattori in "factors") genera instances_per_group istanze e le salva in
<out>/<gruppo>/<istanza>.alb. Scrive anche <out>/manifest.csv, con una riga per
istanza: parametri, seed, OS obiettivo e ottenuta, percorso del file. Lo script
degli esperimenti legge il manifest.

Il seed di ogni istanza deriva da base_seed, dal gruppo e dall'indice: rilanciare
lo script con la stessa configurazione produce file identici.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import zlib
from pathlib import Path

from src.generator import generate
from src.graph import PrecedenceGraph


def group_name(g: dict) -> str:
    return f"n{g['n']}_os{g['order_strength']:g}_r{g['tasks_per_station']}_{g['time_dist']}"


def groups_from_config(cfg: dict) -> list[dict]:
    f = cfg["factors"]
    keys = ("n", "order_strength", "tasks_per_station", "time_dist")
    groups = [dict(zip(keys, combo)) for combo in itertools.product(*(f[k] for k in keys))]
    for extra in cfg.get("extra_groups", []):
        if extra not in groups:
            groups.append(dict(extra))
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("configs/design.json"))
    parser.add_argument("--out", type=Path, default=Path("instances"))
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []

    for g in groups_from_config(cfg):
        gname = group_name(g)
        m = max(2, round(g["n"] / g["tasks_per_station"]))
        count = cfg["instances_per_group"]
        for k in range(count):
            # Seed stabile: dipende solo da configurazione, gruppo e indice.
            seed = zlib.crc32(f"{cfg['base_seed']}|{gname}|{k}".encode())
            name = f"{gname}_{k:02d}"
            inst = generate(
                g["n"], m, g["order_strength"],
                time_dist=g["time_dist"], t_min=cfg["t_min"], t_max=cfg["t_max"],
                seed=seed, name=name,
            )
            path = args.out / gname / f"{name}.alb"
            inst.save(path)
            rows.append({
                "instance": name, "group": gname, "path": path.as_posix(),
                "n": g["n"], "m": m, "tasks_per_station": g["tasks_per_station"],
                "time_dist": g["time_dist"], "seed": seed,
                "os_target": g["order_strength"],
                "os": round(PrecedenceGraph(inst).order_strength, 4),
                "n_arcs": inst.n_precedences, "total_time": inst.total_time,
            })
        print(f"{gname}: {count} istanze, m = {m}")
    with (args.out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Totale {len(rows)} istanze. Manifest: {args.out / 'manifest.csv'}")


if __name__ == "__main__":
    main()