"""Tabelle e grafici dai risultati degli esperimenti.

Uso:
    python -m scripts.make_figures --results results/results.csv \\
        --out results/figures_results/ --time-limit 180

Legge il CSV scritto da run_experiments.py (o dal menù, src/main.py) e produce,
nella cartella --out:

    tabella_riassunto.csv     per metodo, sul totale e per numero di task
    tabella_pli.csv           per gruppo e modello: % di ottimi dimostrati, tempo
                              medio, gap medio al termine, esecuzioni senza soluzione
    tabella_euristiche.csv    per gruppo ed euristica: scarto medio e massimo dal
                              riferimento, % di istanze in cui eguaglia il miglior
                              valore noto
    confronto_euristiche.csv  gruppi contro Hoffmann: vittorie, pareggi, sconfitte
                              e test di Wilcoxon (se scipy è installato)
    tabella_distribuzioni_100.csv  a 100 task: riepilogo per metodo, tempi uniformi e bimodali                          
    pli_ottimi.png            % di istanze risolte all'ottimo dimostrato
    pli_tempi.png             tempo medio di calcolo
    pli_gap.png               gap medio tra soluzione e lower bound al termine
    euristiche_scarto.png     scarto medio dal miglior lower bound
    euristiche_migliore.png   % di istanze in cui l'euristica eguaglia il miglior
                              valore noto
    euristiche_ottimo.png     % di istanze con ottimo noto in cui l'euristica lo raggiunge;
    distribuzioni_*.png            a 100 task: gli stessi grafici, una colonna per distribuzione

Ogni grafico è una griglia di pannelli che segue il disegno sperimentale: una
colonna per numero di task, una riga per order strength; dentro ogni pannello,
un gruppo di barre per numero di stazioni e una barra per metodo. I grafici principali usano i soli tempi uniformi; 
i gruppi con tempi bimodali (100 task) hanno grafici a parte

Riferimento per le euristiche. Per ogni istanza:
    miglior lower bound = massimo dei lower bound di tutti i metodi (ognuno è valido);
    miglior valore noto = minimo degli obiettivi di tutti i metodi.
Se i due coincidono l'ottimo è dimostrato. Lo scarto di un'euristica è
(obiettivo - miglior lower bound) / miglior lower bound: è la distanza dall'ottimo
quando l'ottimo è dimostrato, e un limite superiore a quella distanza altrimenti.

Le funzioni di questo modulo si possono anche importare:

    from scripts.make_figures import load_results, plot_grid
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
    "patterson_albracht": ("Patterson & Albracht", "#2a78d6"),
    "ritt_costa": ("Ritt & Costa", "#1baf7a"),
    "hoffmann": ("Hoffmann", "#eda100"),
    "gruppi": ("Gruppi", "#4a3aa7"),
}
PLI = ["patterson_albracht", "ritt_costa"]
HEURISTICS = ["hoffmann", "gruppi"]

# Il fattore "numero di stazioni" è memorizzato come task per stazione: m = n / valore.
STATION_LABELS = {3: "tante\n(n/3)", 6: "medie\n(n/6)", 10: "poche\n(n/10)"}

INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dc", "#fcfcfb"


# ----------------------------------------------------------------- dati


def load_results(path: str | Path) -> pd.DataFrame:
    """Legge il CSV dei risultati e aggiunge i riferimenti per istanza.

    Le righe di metodi non presenti in METHODS vengono scartate (con un avviso):
    così un file che contiene ancora esecuzioni di un modello rimosso dal
    progetto si analizza comunque, e i riferimenti usano solo i metodi attuali.

    Colonne aggiunte: os_target (order strength obiettivo del gruppo), best_lb,
    best_ub, proven (ottimo dimostrato per l'istanza), dev (scarto dell'obiettivo
    dal miglior lower bound), is_best (eguaglia il miglior valore noto).
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


def summary_table(df: pd.DataFrame, by: str = "n") -> pd.DataFrame:
    """Una riga per metodo sul totale, poi una per metodo e valore di `by`
    (numero di task, oppure distribuzione dei tempi)."""
    order = [m for m in METHODS if m in set(df["method"])]

    def block(data: pd.DataFrame, label) -> pd.DataFrame:
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
        ).reindex(order).dropna(how="all")
        out.insert(0, by, label)
        return out.reset_index()

    parts = [block(df, "tutti")] if by == "n" else []
    parts += [block(part, key) for key, part in df.groupby(by)]
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
        istanze_con_ottimo_dimostrato=("proven", "sum"),
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


# ----------------------------------------------------------------- grafici

DIST_LABELS = {"uniform": "uniformi", "bimodal": "bimodali"}

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
    columns: str = "n",
    scale: float = 1.0,
    reference_line: float | None = None,
    reference_label: str = "",
) -> None:
    """Griglia di pannelli: colonne = numero di task (o distribuzione dei tempi),
    righe = order strength.

    In ogni pannello un gruppo di barre per numero di stazioni e una barra per
    metodo. L'asse verticale è lo stesso in tutti i pannelli, così le altezze
    si confrontano tra un pannello e l'altro.

    Args:
        data: righe dei risultati (da load_results), già filtrate se serve.
        value: colonna da aggregare (per esempio "time_s", "gap", "dev").
        methods: metodi da disegnare, nell'ordine voluto.
        columns: "n" per una colonna per numero di task, "time_dist" per una
            colonna per distribuzione dei tempi.
        scale: fattore applicato ai valori (100 per passare a percentuali).
        reference_line: linea orizzontale di riferimento (per esempio il limite di tempo).
    """
    grid = data
    methods = [m for m in methods if m in set(grid["method"])]
    if not methods:
        print(f"  (nessun dato per {Path(path).name}: saltato)")
        return

    # Tempi uniformi per primi; per il numero di task, ordine crescente.
    ns = sorted(grid[columns].unique(), key=lambda v: (v != "uniform", v))
    oss = sorted(grid["os_target"].unique())
    ratios = sorted(grid["tasks_per_station"].unique())
    table = grid.groupby(["os_target", columns, "tasks_per_station", "method"])[value].mean() * scale
    # Istanze per gruppo, per ogni colonna (il valore più frequente tra i suoi gruppi).
    per_group = grid.groupby([columns, "group"])["instance"].nunique().groupby(columns).agg(
        lambda s: int(s.mode().iloc[0])
    )

    fig, axes = plt.subplots(
        len(oss), len(ns), sharex=True, sharey=True, squeeze=False,
        figsize=(max(9.5, 1.2 + 2.5 * len(ns)), 1.6 + 1.9 * len(oss))
    )
    width = 0.8 / len(methods)
    # Stesso asse verticale in tutti i pannelli, con un margine sopra la barra più alta.
    shown = table[table.index.get_level_values("method").isin(methods)]
    y_top = max(float(shown.max()) if len(shown) else 0.0, reference_line or 0.0)
    y_top = y_top * 1.1 if y_top > 0 else 1.0
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
                  head = f"{int(n)} task" if columns == "n" else f"tempi {DIST_LABELS.get(n, n)}"
                  ax.set_title(f"{head}\n({per_group[n]} istanze per gruppo)", fontsize=9, color=INK, pad=6)
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
    col_text = "numero di task" if columns == "n" else "distribuzione dei tempi"
    how_to_read = (f"{ylabel}. Colonne: {col_text}. Righe: order strength (OS). "
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


def make_all(results: str | Path, out: str | Path, time_limit: float | None = None) -> None:
    """Scrive tutte le tabelle e tutti i grafici nella cartella out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_results(results)
    print(f"{df['instance'].nunique()} istanze, metodi: {[m for m in METHODS if m in set(df['method'])]}")
    # Analisi principale sul disegno fattoriale (tempi uniformi); i tempi
    # bimodali, presenti solo a 100 task, hanno un confronto a parte.
    uni = df[df["time_dist"] == "uniform"]
    n_dist = df.loc[df["n"] == 100, "time_dist"].nunique()

    summary_table(uni).to_csv(out / "tabella_riassunto.csv", index=False)
    pli_table(df).to_csv(out / "tabella_pli.csv", index=False)
    heuristic_table(df).to_csv(out / "tabella_euristiche.csv", index=False)
    comparison = heuristic_comparison(uni)
    if not comparison.empty:
        comparison.to_csv(out / "confronto_euristiche.csv", index=False)
    if n_dist > 1:
        summary_table(df[df["n"] == 100], by="time_dist").to_csv(
            out / "tabella_distribuzioni_100.csv", index=False)
    print(f"  tabelle in {out}")

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
    for data, value, methods, scale, title, ylabel, name, ref in figures:
        extra = {"reference_line": ref, "reference_label": "limite di tempo"} if ref else {}
        plot_grid(data[data["time_dist"] == "uniform"], value, methods, scale=scale,
                  title=title, ylabel=ylabel, path=out / f"{name}.png", **extra)
        if n_dist > 1:
            plot_grid(data[data["n"] == 100], value, methods, scale=scale, columns="time_dist",
                      title=f"100 task, tempi uniformi e bimodali. {title}",
                      ylabel=ylabel, path=out / f"distribuzioni_{name}.png", **extra)


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
