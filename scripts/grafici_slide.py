"""Tabelle per i grafici delle slide dei risultati, da results/results.csv.

Uso:
    python -m scripts.grafici_slide --results results/results.csv --out results/grafici_slide/

Ogni CSV ha la forma da incollare in un grafico di PowerPoint: prima colonna le
categorie dell'asse, poi una colonna per serie. I numeri sono con la virgola
decimale e il separatore ";" (formato di Excel/PowerPoint in italiano).

Definizioni (le stesse di make_figures.py):
    ottimo dimostrato da un metodo  status == "optimal" (soluzione = proprio lower bound);
    istanza chiusa dai PLI          almeno uno dei due PLI dimostra l'ottimo;
    miglior lower bound             massimo dei lower bound di tutti i metodi;
    miglior valore                  minimo degli obiettivi di tutti i metodi;
    ottimo noto                     miglior valore = miglior lower bound;
    gap / scarto                    (valore - miglior lower bound) / miglior lower bound.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PLI = ["patterson_albracht", "ritt_costa"]
DIST = {"uniform": "Uniforme", "bimodal": "Bimodale"}
STAZIONI = {3: "tante (n/3)", 6: "medie (n/6)", 10: "poche (n/10)"}


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["os_target"] = df["group"].str.extract(r"_os([0-9.]+)_")[0].astype(float)
    df["lb"] = np.ceil(df["lower_bound"] - 1e-6)        # c è intero
    return df


def per_instance(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per istanza, con i valori di ogni metodo e i riferimenti."""
    keys = ["instance", "time_dist", "n", "tasks_per_station", "os_target"]
    inst = df.drop_duplicates("instance").set_index("instance")[keys[1:]]
    obj = df.pivot(index="instance", columns="method", values="objective")
    opt = df.pivot(index="instance", columns="method", values="status") == "optimal"
    inst["best_lb"] = df.groupby("instance")["lb"].max()
    inst["best_ub"] = obj.min(axis=1)
    inst["noto"] = inst["best_ub"] == inst["best_lb"]
    inst["chiusa_pli"] = opt[PLI].any(axis=1)
    inst["pli"] = obj[PLI].min(axis=1)
    inst["hoffmann"] = obj["hoffmann"]
    inst["gruppi"] = obj["gruppi"]
    cmin = df[df["kind"] == "pli"].drop_duplicates("instance").set_index("instance")["extra"]
    inst["c_min"] = cmin.map(lambda s: json.loads(s)["c_min"])
    lb_pli = df[df["kind"] == "pli"].groupby("instance")["lb"].max()
    inst["lb_pli"] = lb_pli
    return inst


def wide(series: pd.Series, index_name: str, labels: dict | None = None) -> pd.DataFrame:
    """Da una serie con indice (time_dist, categoria) a una colonna per distribuzione."""
    t = series.unstack("time_dist")[list(DIST)].rename(columns=DIST)
    if labels:
        t.index = t.index.map(labels)
    t.index.name = index_name
    return t


def by_group(t: pd.DataFrame) -> pd.DataFrame:
    """Righe nell'ordine Uniforme poi Bimodale, stazioni tante, medie, poche."""
    order = [(d, r) for d in DIST for r in STAZIONI if (d, r) in t.index]
    t = t.loc[order]
    t.index = [f"{DIST[d]}, {STAZIONI[r]}" for d, r in t.index]
    t.index.name = "Gruppo"
    return t


def save(table: pd.DataFrame, out: Path, name: str, decimals: int = 1) -> None:
    table.round(decimals).to_csv(out / name, sep=";", decimal=",")
    print(f"\n{name}\n{table.round(decimals).to_string()}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--results", type=Path, default=Path("results/results.csv"))
    p.add_argument("--out", type=Path, default=Path("results/grafici_slide"))
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    df = load(a.results)
    inst = per_instance(df)
    pli = df[df["kind"] == "pli"].copy()
    pli["ottimo"] = pli["status"] == "optimal"

    # Slide "Chiusura dei PLI e tempi"
    save(wide(inst.groupby(["time_dist", "n"])["chiusa_pli"].mean() * 100, "Numero di task"),
         a.out, "chiusura_per_n.csv")
    t = pli.groupby(["n", "time_dist", "method"])["time_s"].mean().unstack(["time_dist", "method"])
    t = t[[("uniform", PLI[0]), ("uniform", PLI[1]), ("bimodal", PLI[0]), ("bimodal", PLI[1])]]
    t.columns = ["PA unif.", "RC unif.", "PA bim.", "RC bim."]
    t.index.name = "Numero di task"
    save(t, a.out, "tempi_pli_per_n.csv", decimals=2)

    # Slide "Cosa rende difficile un'istanza"
    save(wide(inst.groupby(["time_dist", "tasks_per_station"])["chiusa_pli"].mean() * 100,
              "Numero di stazioni", STAZIONI), a.out, "chiusura_per_stazioni.csv")
    save(wide(inst.groupby(["time_dist", "os_target"])["chiusa_pli"].mean() * 100, "OS"),
         a.out, "chiusura_per_os.csv")

    # Slide "PA vs RC": ottimi dimostrati per OS (su 300 istanze)
    t = pli.groupby(["os_target", "time_dist", "method"])["ottimo"].sum().unstack(["time_dist", "method"])
    t = t[[("uniform", PLI[0]), ("uniform", PLI[1]), ("bimodal", PLI[0]), ("bimodal", PLI[1])]]
    t.columns = ["PA unif.", "RC unif.", "PA bim.", "RC bim."]
    t.index.name = "OS"
    save(t, a.out, "pa_rc_per_os.csv", decimals=0)

    # Slide "Dove i modelli differiscono di più": tutti i gruppi, dal più diverso
    g = pli.groupby(["group", "method"])["ottimo"].mean().unstack() * 100
    g = g.rename(columns={PLI[0]: "PA (%)", PLI[1]: "RC (%)"})
    g["differenza"] = (g["RC (%)"] - g["PA (%)"]).abs()
    save(g.sort_values("differenza", ascending=False).head(10), a.out, "pa_rc_gruppi.csv", decimals=0)

    # Slide "Hoffmann vs Gruppi": % di istanze con ottimo noto in cui l'euristica lo trova
    noti = inst[inst["noto"]]
    rows = {}
    for method in ("hoffmann", "gruppi"):
        hit = (noti[method] == noti["best_ub"]).groupby([noti["n"], noti["time_dist"]]).mean() * 100
        for dist in DIST:
            rows[f"{method.capitalize()} {DIST[dist].lower()}"] = hit.xs(dist, level="time_dist")
    t = pd.DataFrame(rows)[["Hoffmann uniforme", "Gruppi uniforme", "Hoffmann bimodale", "Gruppi bimodale"]]
    t.index.name = "Numero di task"
    save(t, a.out, "hoffmann_gruppi_ottimo.csv")

    # Slide "Hoffmann vs PLI": istanze in cui vince Hoffmann, pari, vince il miglior PLI
    d = inst["hoffmann"] - inst["pli"]
    t = pd.DataFrame({"Vince Hoffmann": d < 0, "Pari": d == 0, "Vince il miglior PLI": d > 0})
    t = t.groupby([inst["n"], inst["time_dist"]]).sum()
    t.index = [f"{n}, {'unif.' if dist == 'uniform' else 'bim.'}" for n, dist in t.index]
    t = t.loc[[f"{n}, {s}" for n in sorted(inst["n"].unique()) for s in ("unif.", "bim.")]]
    t.index.name = "Gruppo"
    save(t, a.out, "hoffmann_vs_pli.csv", decimals=0)

    # Slide "Perché i PLI non chiudono": solo le istanze che nessun PLI chiude
    op = inst[~inst["chiusa_pli"]].copy()
    op["gap_pli"] = (op["pli"] - op["best_lb"]) / op["best_lb"] * 100
    op["gap_hoffmann"] = (op["hoffmann"] - op["best_lb"]) / op["best_lb"] * 100
    op["vince_h"] = op["hoffmann"] < op["pli"]
    op["pari"] = op["hoffmann"] == op["pli"]
    op["vince_pli"] = op["hoffmann"] > op["pli"]
    op["h_ottimo"] = op["hoffmann"] == op["best_lb"]
    k = [op["time_dist"], op["tasks_per_station"]]
    t = op.groupby(k).agg(**{"Vince Hoffmann": ("vince_h", "sum"), "Pari": ("pari", "sum"),
                             "Vince il miglior PLI": ("vince_pli", "sum")})
    save(by_group(t), a.out, "non_chiuse_esito.csv", decimals=0)
    t = op.groupby(k).agg(istanze=("pli", "size"), gap_miglior_pli=("gap_pli", "mean"),
                          gap_hoffmann=("gap_hoffmann", "mean"), hoffmann_trova_ottimo=("h_ottimo", "sum"))
    save(by_group(t), a.out, "non_chiuse_gap.csv", decimals=2)

    # Lower bound debole con tante stazioni: istanze chiuse e aperte (miglior soluzione vs miglior LB)
    k = [inst["time_dist"], inst["tasks_per_station"]]
    closed = inst["noto"]
    sopra = (inst["best_ub"] > inst["c_min"]) & closed
    scarto = ((inst["best_ub"] - inst["c_min"]) / inst["c_min"] * 100).where(closed)
    alzato = (inst["lb_pli"] > inst["c_min"]) & ~closed
    t = pd.DataFrame({
        "chiuse": closed.groupby(k).sum(),
        "ottimo sopra il LB combinatorio (%)": sopra.groupby(k).sum() / closed.groupby(k).sum() * 100,
        "di quanto in media (%)": scarto.groupby(k).mean(),
        "aperte": (~closed).groupby(k).sum(),
        "aperte con LB alzato dal solver (%)": alzato.groupby(k).sum() / (~closed).groupby(k).sum() * 100,
    })
    save(by_group(t), a.out, "bound_debole.csv")


if __name__ == "__main__":
    main()