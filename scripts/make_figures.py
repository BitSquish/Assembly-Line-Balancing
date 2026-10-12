"""Tabelle e grafici dai risultati degli esperimenti.

Uso:
    python -m scripts.make_figures --results results/results.csv \\
        --out results/figures_results/ --time-limit 180

Legge il CSV scritto da run_experiments.py (o dal menù, src/main.py) e produce,
nella cartella --out:

    tabella_riassunto.csv       per distribuzione dei tempi e metodo, sul totale
                                e per numero di task
    tabella_pli.csv             per gruppo e modello: % di ottimi dimostrati, tempo
                                medio, gap medio al termine, esecuzioni senza soluzione
    tabella_euristiche.csv      per gruppo ed euristica: scarto medio e massimo dal
                                riferimento, % di istanze in cui eguaglia il miglior
                                valore noto, ottimo raggiunto
    confronto_euristiche.csv    gruppi contro Hoffmann, per gruppo e per
                                distribuzione: vittorie, pareggi, sconfitte e test
                                di Wilcoxon (se scipy è installato)
    confronto_hoffmann_pli.csv  Hoffmann contro il migliore dei due PLI, per
                                distribuzione e numero di task, con test di Wilcoxon

e sei grafici, ciascuno in due versioni (<nome>_uniform.png e <nome>_bimodal.png):

    pli_ottimi                  % di istanze risolte all'ottimo dimostrato
    pli_tempi                   tempo medio di calcolo
    pli_gap                     gap medio tra soluzione e lower bound al termine
    euristiche_scarto           scarto medio dal miglior lower bound
    euristiche_migliore         % di istanze in cui l'euristica eguaglia il miglior
                                valore noto
    euristiche_ottimo           % di istanze con ottimo noto in cui l'euristica lo
                                raggiunge
    confronto_distribuzioni     tempi uniformi contro bimodali, per numero di task:
                                istanze chiuse, tempo medio dei PLI, Hoffmann contro
                                il miglior PLI

Ogni grafico è una griglia di pannelli che segue il disegno sperimentale: una
colonna per numero di task, una riga per order strength; dentro ogni pannello,
un gruppo di barre per numero di stazioni e una barra per metodo. Le due
versioni di un grafico hanno lo stesso asse verticale, così si confrontano.

Riferimento per le euristiche. Per ogni istanza:
    miglior lower bound = massimo dei lower bound di tutti i metodi (ognuno è valido);
    miglior valore noto = minimo degli obiettivi di tutti i metodi.
Se i due coincidono l'ottimo è dimostrato. Lo scarto di un'euristica è
(obiettivo - miglior lower bound) / miglior lower bound: è la distanza dall'ottimo
quando l'ottimo è dimostrato, e un limite superiore a quella distanza altrimenti.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                       # nessuna finestra: si salva solo su file
import matplotlib.pyplot as plt
import pandas as pd

# Colore fisso per metodo (segue il metodo, non la posizione nel grafico).
METHODS = {
    "patterson_albracht": ("Patterson & Albracht", "#5293e3"),
    "ritt_costa": ("Ritt & Costa", "#25ba85"),
    "hoffmann": ("Hoffmann", "#fab3ff"),
    "gruppi": ("Gruppi", "#990c2b"),
}
PLI = ["patterson_albracht", "ritt_costa"]
HEURISTICS = ["hoffmann", "gruppi"]

# Il fattore "numero di stazioni" è memorizzato come task per stazione: m = n / valore.
STATION_LABELS = {3: "tante\n(n/3)", 6: "medie\n(n/6)", 10: "poche\n(n/10)"}
DIST_LABELS = {"uniform": "uniformi", "bimodal": "bimodali"}
DIST_COLORS = {"uniform": "#71f116", "bimodal": "#7c1c78"}
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dc", "#fcfcfb"


# ----------------------------------------------------------------- dati


def load_results(path: str | Path) -> pd.DataFrame:
    """Legge il CSV dei risultati e aggiunge i riferimenti per istanza.

    Le righe di metodi non presenti in METHODS vengono scartate (con un avviso):
    così un file che contiene ancora esecuzioni di un modello rimosso dal
    progetto si analizza comunque, e i riferimenti usano solo i metodi attuali.

    Colonne aggiunte: os_target (order strength obiettivo del gruppo), best_lb,
    best_ub, proven (ottimo dimostrato per l'istanza), dev (scarto dell'obiettivo
    dal miglior lower bound), is_best (eguaglia il miglior valore noto),
    reached e dev_opt (ottimo raggiunto e scarto dall'ottimo, solo dove
    l'ottimo è noto).
    """
    df = pd.read_csv(path)
    unknown = sorted(set(df["method"]) - set(METHODS))
    if unknown:
        print(f"  Attenzione: righe scartate per metodi non previsti: {unknown}")
        df = df[df["method"].isin(METHODS)].copy()
    errors = int((df["status"] == "error").sum())
    if errors:
        print(f"  Attenzione: {errors} esecuzioni in errore (vedi la colonna 'error' del CSV)")

    for col in ("objective", "lower_bound", "time_s", "gap", "n", "tasks_per_station"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["os_target"] = df["group"].map(_os_from_group)

    per_instance = df.groupby("instance").agg(
        best_lb=("lower_bound", "max"), best_ub=("objective", "min")
    )
    df = df.join(per_instance, on="instance")
    bad = df.loc[df["best_lb"] > df["best_ub"], "instance"].unique()
    if len(bad):
        raise ValueError(f"lower bound sopra la miglior soluzione in {len(bad)} istanze: {list(bad[:5])}")
    df["proven"] = df["best_lb"] == df["best_ub"]
    df["dev"] = (df["objective"] - df["best_lb"]) / df["best_lb"]
    df["is_best"] = df["objective"] == df["best_ub"]
    # Solo dove l'ottimo è noto (istanza chiusa da almeno un metodo): il metodo
    # lo ha raggiunto? E quanto dista? Altrove il valore è mancante e non entra
    # nelle medie.
    df["reached"] = (df["objective"] == df["best_ub"]).where(df["proven"]).astype(float)
    df["dev_opt"] = ((df["objective"] - df["best_ub"]) / df["best_ub"]).where(df["proven"])
    return df


def _os_from_group(group: str) -> float:
    # "n50_os0.2_r3_uniform" -> 0.2 (l'OS obiettivo; la colonna "os" è quella ottenuta)
    return float(next(p[2:] for p in group.split("_") if p.startswith("os")))


_GROUP_KEYS = ["group", "n", "os_target", "tasks_per_station", "time_dist", "method"]


# ----------------------------------------------------------------- tabelle


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per ogni distribuzione dei tempi: una riga per metodo sul totale, poi
    una per metodo e numero di task."""
    order = [m for m in METHODS if m in set(df["method"])]

    def block(data: pd.DataFrame, dist, n) -> pd.DataFrame:
        out = data.groupby("method").agg(
            istanze=("instance", "count"),
            ottimi_pct=("status", lambda s: 100 * (s == "optimal").mean()),
            scarto_medio_pct=("dev", lambda x: 100 * x.mean()),
            scarto_max_pct=("dev", lambda x: 100 * x.max()),
            miglior_valore_pct=("is_best", lambda x: 100 * x.mean()),
            tempo_medio_s=("time_s", "mean"),
            ottimo_noto=("proven", "sum"),
            ottimo_raggiunto_pct=("reached", lambda x: 100 * x.mean()),
            scarto_da_ottimo_pct=("dev_opt", lambda x: 100 * x.mean()),
        ).reindex(order).dropna(how="all").reset_index()
        out.insert(0, "n", n)
        out.insert(0, "time_dist", dist)
        return out

    parts = []
    for dist, part in df.groupby("time_dist", sort=False):
        parts.append(block(part, dist, "tutti"))
        parts += [block(sub, dist, n) for n, sub in part.groupby("n")]
    return pd.concat(parts, ignore_index=True).round(2)


def pli_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "pli"]
    out = d.groupby(_GROUP_KEYS, sort=False).agg(
        istanze=("instance", "count"),
        ottimi_pct=("status", lambda s: 100 * (s == "optimal").mean()),
        tempo_medio_s=("time_s", "mean"),
        gap_medio_pct=("gap", lambda g: 100 * g.mean()),
        senza_soluzione=("status", lambda s: int(s.isin(["no_solution", "error", "solver_error"]).sum())),
    )
    return out.round(2).reset_index()


def heuristic_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "euristica"]
    out = d.groupby(_GROUP_KEYS, sort=False).agg(
        istanze=("instance", "count"),
        scarto_medio_pct=("dev", lambda x: 100 * x.mean()),
        scarto_max_pct=("dev", lambda x: 100 * x.max()),
        miglior_valore_pct=("is_best", lambda x: 100 * x.mean()),
        tempo_medio_s=("time_s", "mean"),
        ottimo_noto=("proven", "sum"),
        ottimo_raggiunto_pct=("reached", lambda x: 100 * x.mean()),
        scarto_da_ottimo_pct=("dev_opt", lambda x: 100 * x.mean()),
    )
    return out.round(3).reset_index()


def heuristic_comparison(df: pd.DataFrame, a: str = "gruppi", b: str = "hoffmann") -> pd.DataFrame:
    """Confronto appaiato a contro b, per gruppo e sul totale.

    Il test dei ranghi con segno di Wilcoxon (Otto et al., 2013, sez. 6.1) dice se
    la differenza tra le due euristiche sulle stesse istanze è significativa.
    """
    wide = df[df["method"].isin([a, b])].pivot(index="instance", columns="method", values="objective")
    if a not in wide or b not in wide:
        return pd.DataFrame()
    wide = wide.dropna().join(df.drop_duplicates("instance").set_index("instance")["group"])

    try:
        from scipy.stats import wilcoxon
    except ImportError:
        wilcoxon = None

    rows = []
    for name, part in [*wide.groupby("group", sort=False), ("TOTALE", wide)]:
        diff = part[a] - part[b]
        p_value = None
        if wilcoxon is not None and (diff != 0).sum() >= 1:
            p_value = float(wilcoxon(part[a], part[b]).pvalue)
        rows.append({
            "group": name, "istanze": len(part),
            f"{a}_meglio": int((diff < 0).sum()), "pari": int((diff == 0).sum()),
            f"{b}_meglio": int((diff > 0).sum()),
            "differenza_media_pct": round(100 * (diff / part[b]).mean(), 3),
            "wilcoxon_p": p_value,
        })
    return pd.DataFrame(rows)


def hoffmann_vs_pli(df: pd.DataFrame) -> pd.DataFrame:
    """Hoffmann contro il migliore dei due PLI, per distribuzione dei tempi e numero di task.

    Per ogni istanza si confronta l'obiettivo di Hoffmann con il minimo tra gli
    obiettivi dei PLI; test di Wilcoxon sulle coppie (Otto et al., 2013, sez. 6.1).
    """
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        wilcoxon = None

    wide = df.pivot(index="instance", columns="method", values="objective")
    if "hoffmann" not in wide or not set(PLI) <= set(wide.columns):
        return pd.DataFrame()
    info = df.drop_duplicates("instance").set_index("instance")[["time_dist", "n"]]
    wide = wide.join(info)
    wide["best_pli"] = wide[PLI].min(axis=1)
    rows = []
    for (dist, n), part in wide.groupby(["time_dist", "n"]):
        diff = part["hoffmann"] - part["best_pli"]
        p_value = None
        if wilcoxon is not None and (diff != 0).any():
            p_value = float(wilcoxon(part["hoffmann"], part["best_pli"]).pvalue)
        rows.append({
            "time_dist": dist, "n": n, "istanze": len(part),
            "hoffmann_meglio": int((diff < 0).sum()), "pari": int((diff == 0).sum()),
            "pli_meglio": int((diff > 0).sum()), "wilcoxon_p": p_value,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- grafici


def _fmt(value: float) -> str:
    """Numero con la virgola decimale e senza zeri inutili: 0.2 -> '0,2', 50.0 -> '50'."""
    return f"{value:g}".replace(".", ",")


def plot_grid(
    data: pd.DataFrame,
    value: str,
    methods: list[str],
    *,
    title: str,
    ylabel: str,
    path: str | Path,
    scale: float = 1.0,
    reference_line: float | None = None,
    reference_label: str = "",
    y_max: float | None = None,
) -> None:
    """Griglia di pannelli: colonne = numero di task, righe = order strength.

    In ogni pannello un gruppo di barre per numero di stazioni e una barra per
    metodo. L'asse verticale è lo stesso in tutti i pannelli, così le altezze
    si confrontano tra un pannello e l'altro.

    Args:
        data: righe dei risultati (da load_results), già filtrate se serve.
        value: colonna da aggregare (per esempio "time_s", "gap", "dev").
        methods: metodi da disegnare, nell'ordine voluto.
        scale: fattore applicato ai valori (100 per passare a percentuali).
        reference_line: linea orizzontale di riferimento (per esempio il limite di tempo).
        y_max: estremo dell'asse verticale. Passando lo stesso valore a più
            grafici (per esempio uniformi e bimodali) le altezze si confrontano.
    """
    methods = [m for m in methods if m in set(data["method"])]
    if not methods:
        print(f"  (nessun dato per {Path(path).name}: saltato)")
        return

    ns = sorted(data["n"].unique())
    oss = sorted(data["os_target"].unique())
    ratios = sorted(data["tasks_per_station"].unique())
    table = data.groupby(["os_target", "n", "tasks_per_station", "method"])[value].mean() * scale
    # Istanze per gruppo, per ogni numero di task (il valore più frequente tra i suoi gruppi).
    per_group = data.groupby(["n", "group"])["instance"].nunique().groupby("n").agg(
        lambda s: int(s.mode().iloc[0])
    )

    fig, axes = plt.subplots(
        len(oss), len(ns), sharex=True, sharey=True, squeeze=False,
        figsize=(max(9.5, 1.2 + 2.5 * len(ns)), 1.6 + 1.9 * len(oss))
    )
    width = 0.8 / len(methods)
    # Stesso asse verticale in tutti i pannelli, con un margine sopra la barra più alta.
    if y_max is None:
        shown = table[table.index.get_level_values("method").isin(methods)]
        y_max = max(float(shown.max()) if len(shown) else 0.0, reference_line or 0.0)
    y_top = y_max * 1.1 if y_max > 0 else 1.0
    for row, os_value in enumerate(oss):
        for col, n in enumerate(ns):
            ax = axes[row][col]
            ax.set_facecolor(SURFACE)
            drawn = False
            for k, method in enumerate(methods):
                label, color = METHODS[method]
                heights = [table.get((os_value, n, r, method), float("nan")) for r in ratios]
                if all(pd.isna(h) for h in heights):
                    continue
                drawn = True
                x = [g + (k - (len(methods) - 1) / 2) * width for g in range(len(ratios))]
                # Lo spazio tra le barre è lasciato alla superficie (bordo dello stesso colore).
                ax.bar(x, [0 if pd.isna(h) else h for h in heights], width=width, color=color,
                       label=label, edgecolor=SURFACE, linewidth=1.5, zorder=3)
                # Una barra troppo bassa non si vede: si scrive il valore, così un
                # numero piccolo si distingue da un dato mancante.
                for xk, h in zip(x, heights):
                    if pd.isna(h):
                        text, base = "n.d.", 0.0
                    elif h < y_top * 0.04:
                        text, base = _fmt(round(h, 2)), h
                    else:
                        continue
                    ax.text(xk, base + y_top * 0.015, text, ha="center", va="bottom",
                            fontsize=6.5, color=INK_MUTED, zorder=4)
            if not drawn:
                ax.text(0.5, 0.5, "nessun dato", transform=ax.transAxes, ha="center",
                        va="center", fontsize=8, color=INK_MUTED)
            if reference_line is not None:
                ax.axhline(reference_line, color=INK_MUTED, linewidth=1, linestyle=(0, (4, 3)),
                           zorder=2)

            if row == 0:
                ax.set_title(f"{int(n)} task\n({per_group[n]} istanze per gruppo)",
                             fontsize=9, color=INK, pad=6)
            if col == 0:
                ax.set_ylabel(f"OS {_fmt(os_value)}", fontsize=9, color=INK)
            ax.set_xticks(range(len(ratios)))
            ax.set_xticklabels(
                [STATION_LABELS.get(int(r), f"n/{_fmt(r)}") for r in ratios],
                fontsize=7.5, color=INK_MUTED,
            )
            ax.set_ylim(0, y_top)
            ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=1)
            ax.set_axisbelow(True)
            ax.tick_params(axis="both", length=0, labelcolor=INK_MUTED, labelsize=7.5)
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
            ax.spines["bottom"].set_color(GRID)

    # Intestazione: titolo, legenda e una riga che spiega come leggere la griglia.
    height = fig.get_figheight()
    top = 1 - 0.80 / height                 # 0,80 pollici riservati all'intestazione
    fig.suptitle(title, x=0.01, y=1 - 0.08 / height, ha="left", va="top",
                 fontsize=11, color=INK)
    how_to_read = (f"{ylabel}. Colonne: numero di task. Righe: order strength (OS). "
                   "Asse orizzontale: numero di stazioni m.")
    if reference_line is not None and reference_label:
        how_to_read += f" Linea tratteggiata: {reference_label}."
    fig.text(0.01, 1 - 0.40 / height, how_to_read,
             ha="left", va="top", fontsize=8, color=INK_MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=METHODS[m][1]) for m in methods]
    fig.legend(handles, [METHODS[m][0] for m in methods], loc="upper left",
               bbox_to_anchor=(0.005, 1 - 0.58 / height), ncol=len(methods), frameon=False,
               fontsize=8.5, labelcolor=INK, handlelength=1.1, borderaxespad=0)

    fig.tight_layout(rect=(0, 0, 1, top))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")


def plot_distributions(df: pd.DataFrame, path: str | Path) -> None:
    """Confronto diretto tra tempi uniformi e bimodali, per numero di task.

    Tre pannelli: % di istanze chiuse (ottimo dimostrato da almeno un metodo),
    tempo medio dei PLI ed esito del confronto tra Hoffmann e il migliore dei
    due PLI, con il p-value del test di Wilcoxon.
    """
    dists = [d for d in ("uniform", "bimodal") if d in set(df["time_dist"])]
    ns = sorted(df["n"].unique())
    inst = df.drop_duplicates("instance")
    closed = inst.groupby(["time_dist", "n"])["proven"].mean() * 100
    pli_time = df[df["kind"] == "pli"].groupby(["time_dist", "n"])["time_s"].mean()
    versus = hoffmann_vs_pli(df).set_index(["time_dist", "n"])

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2),
                             gridspec_kw={"width_ratios": [1, 1, 1.35]})
    width = 0.38
    for ax, series, label, fmt in (
        (axes[0], closed, "Istanze chiuse (%)", lambda v: f"{v:.0f}"),
        (axes[1], pli_time, "Tempo medio dei PLI (s)", lambda v: f"{v:.0f}" if v >= 1 else _fmt(round(v, 2))),
    ):
        for k, dist in enumerate(dists):
            x = [i + (k - (len(dists) - 1) / 2) * width for i in range(len(ns))]
            h = [series.get((dist, n), 0.0) for n in ns]
            ax.bar(x, h, width=width, color=DIST_COLORS[dist], edgecolor=SURFACE,
                   linewidth=1.5, zorder=3, label=f"tempi {DIST_LABELS[dist]}")
            for xk, hk in zip(x, h):
                ax.text(xk, hk, fmt(hk), ha="center", va="bottom", fontsize=7.5, color=INK_MUTED)
        ax.set_title(label, fontsize=10, color=INK, loc="left")
        ax.set_xticks(range(len(ns)))
        ax.set_xticklabels([f"{n} task" for n in ns], fontsize=8.5, color=INK_MUTED)
        ax.set_yticks([])
        ax.tick_params(length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
    axes[0].set_ylim(0, 112)
    axes[1].set_ylim(0, pli_time.max() * 1.15)

    # Terzo pannello: barre al 100% per esito, una per distribuzione e numero di task.
    ax = axes[2]
    parts = [("hoffmann_meglio", "Hoffmann migliore", METHODS["hoffmann"][1]),
             ("pari", "pari", GRID),
             ("pli_meglio", "miglior PLI migliore", "#6f6e69")]
    labels, y = [], 0
    for n in ns:
        for dist in dists:
            if (dist, n) not in versus.index:
                continue
            row = versus.loc[(dist, n)]
            left = 0.0
            for col, name, color in parts:
                share = 100 * row[col] / row["istanze"]
                ax.barh(y, share, left=left, color=color, edgecolor=SURFACE, height=0.8,
                        label=name if y == 0 else None)
                if share >= 7:
                    ax.text(left + share / 2, y, f"{int(row[col])}", ha="center", va="center",
                            fontsize=7.5, color="white" if col != "pari" else INK)
                left += share
            p = row["wilcoxon_p"]
            note = "" if pd.isna(p) else ("p<0,001" if p < 0.001 else f"p={_fmt(round(p, 2))}")
            ax.text(101, y, note, va="center", fontsize=7, color=INK_MUTED)
            labels.append(f"{n} task, {DIST_LABELS[dist]}")
            y += 1
        y += 0.4
    ticks = [k + 0.4 * (k // len(dists)) for k in range(len(labels))]
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels, fontsize=8, color=INK_MUTED)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title("Hoffmann contro il miglior PLI (istanze)", fontsize=10, color=INK, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.02), ncol=3, frameon=False, fontsize=8)
    ax.tick_params(length=0)

    handles = [plt.Rectangle((0, 0), 1, 1, color=DIST_COLORS[d]) for d in dists]
    fig.legend(handles, [f"tempi {DIST_LABELS[d]}" for d in dists], loc="upper left",
               bbox_to_anchor=(0.005, 0.95), ncol=len(dists), frameon=False, fontsize=8.5)
    fig.suptitle("Tempi uniformi e bimodali: con i bimodali i PLI chiudono quasi tutto",
                 x=0.01, ha="left", fontsize=11.5, color=INK)
    fig.patch.set_facecolor(SURFACE)
    for a in axes:
        a.set_facecolor(SURFACE)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")


# ----------------------------------------------------------------- tutto


def make_all(results: str | Path, out: str | Path, time_limit: float | None = None) -> None:
    """Scrive tutte le tabelle e tutti i grafici nella cartella out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_results(results)
    print(f"{df['instance'].nunique()} istanze, metodi: {[m for m in METHODS if m in set(df['method'])]}")

    summary_table(df).to_csv(out / "tabella_riassunto.csv", index=False)
    pli_table(df).to_csv(out / "tabella_pli.csv", index=False)
    heuristic_table(df).to_csv(out / "tabella_euristiche.csv", index=False)
    comparison = pd.concat(
        [heuristic_comparison(part).assign(time_dist=dist)
         for dist, part in df.groupby("time_dist", sort=False)],
        ignore_index=True,
    )
    if not comparison.empty:
        comparison.to_csv(out / "confronto_euristiche.csv", index=False)
    versus = hoffmann_vs_pli(df)
    if not versus.empty:
        versus.to_csv(out / "confronto_hoffmann_pli.csv", index=False)
    print(f"  tabelle in {out}")
    if df["time_dist"].nunique() > 1 and not versus.empty:
        plot_distributions(df, out / "confronto_distribuzioni.png")

    pli = df[df["kind"] == "pli"].copy()
    pli["optimal"] = pli["status"] == "optimal"
    heur = df[df["kind"] == "euristica"].copy()
    figures = [
        (pli, "optimal", PLI, 100, "Istanze risolte all'ottimo dimostrato entro il limite di tempo",
         "% di istanze", "pli_ottimi", None),
        (pli, "time_s", PLI, 1, "Tempo medio di calcolo dei modelli PLI",
         "Secondi", "pli_tempi", time_limit),
        (pli, "gap", PLI, 100, "Gap medio tra soluzione e lower bound del modello al termine",
         "Gap (%)", "pli_gap", None),
        (heur, "dev", HEURISTICS, 100, "Scarto medio delle euristiche dal miglior lower bound",
         "Scarto (%)", "euristiche_scarto", None),
        (heur, "is_best", HEURISTICS, 100, "Istanze in cui l'euristica eguaglia il miglior valore noto",
         "% di istanze", "euristiche_migliore", None),
        (heur, "reached", HEURISTICS, 100,
         "Istanze in cui l'euristica raggiunge l'ottimo (dove l'ottimo è noto)",
         "% delle istanze con ottimo noto", "euristiche_ottimo", None),
    ]
    keys = ["time_dist", "os_target", "n", "tasks_per_station", "method"]
    for data, value, methods, scale, title, ylabel, name, ref in figures:
        extra = {"reference_line": ref, "reference_label": "limite di tempo"} if ref else {}
        # Stesso asse verticale per le due distribuzioni: i grafici si confrontano.
        shown = data[data["method"].isin(methods)]
        y_max = max(float(shown.groupby(keys)[value].mean().max() * scale), ref or 0.0)
        for dist, part in data.groupby("time_dist", sort=False):
            plot_grid(part, value, methods, scale=scale, y_max=y_max,
                      title=f"{title} (tempi {DIST_LABELS.get(dist, dist)})", ylabel=ylabel,
                      path=out / f"{name}_{dist}.png", **extra)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=None,
                        help="limite di tempo usato, per disegnarlo nel grafico dei tempi")
    args = parser.parse_args()
    make_all(args.results, args.out, args.time_limit)


if __name__ == "__main__":
    main()