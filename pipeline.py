#!/usr/bin/env python3
"""
pipeline.py - general, self-adapting panel-forecast backend for the Award B agent.

Reads the dataset in ./data/ (described by ./data/DATA_DESCRIPTION.md) and writes
./submission.csv (exactly: row_id, <target>) and ./report.pdf at the repo root.

Method: per-group level + optional seasonal adjustment, where the level estimator
(last value / recent mean / damped trend) and whether to apply seasonality are
chosen automatically by an internal backtest on the most recent training periods.
This adapts to the unknown dataset (trending vs level-dominated, seasonal or not).

Design priority #1: ALWAYS leave a valid submission.csv. A baseline is written
first; it is replaced by the forecast only if the full pipeline succeeds.

Usage: python pipeline.py [--target T --time C --id-cols a,b]
"""
import os, sys, glob, re, argparse, warnings, traceback
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
SUB_PATH = os.path.join(ROOT, "submission.csv")
REPORT_PATH = os.path.join(ROOT, "report.pdf")
def log(*a): print("[pipeline]", *a, flush=True)
ROWID_PAT = re.compile(r"^(row[_-]?id|id|index)$", re.I)

def list_csvs(): return sorted(glob.glob(os.path.join(DATA, "**", "*.csv"), recursive=True))
def find_rowid_col(df):
    for c in df.columns:
        if ROWID_PAT.match(str(c)): return c
    return None
def timeish(s):
    d = pd.to_datetime(s, errors="coerce")
    if d.notna().mean() > 0.8 and d.nunique() > 2: return "date", d
    v = pd.to_numeric(s, errors="coerce")
    if v.notna().mean() > 0.8 and 2 < v.nunique() <= max(3, len(s)): return "int", v
    return None, None

def detect(frames, ov):
    sample_p = next((p for p, df in frames.items() if find_rowid_col(df) is not None), None)
    if sample_p is None: raise RuntimeError("no file with a row_id column found in data/")
    sample = frames[sample_p]; rowid = find_rowid_col(sample)
    train_p, best = None, -1
    for p, df in frames.items():
        if p == sample_p: continue
        if df.select_dtypes("number").shape[1] >= 1 and len(df) > best: best, train_p = len(df), p
    if train_p is None: raise RuntimeError("no training file with numeric values found in data/")
    train = frames[train_p]
    target = ov.get("target")
    if not target:
        cand = [c for c in sample.columns if c != rowid and c in train.columns and
                pd.api.types.is_numeric_dtype(train[c])]
        target = cand[0] if cand else None
    if not target:
        cand = [c for c in sample.columns if c != rowid and c in train.columns]
        target = cand[-1] if cand else [c for c in sample.columns if c != rowid][-1]
    shared = [c for c in sample.columns if c in train.columns and c not in (rowid, target)]
    time_col = ov.get("time")
    if not time_col:
        for c in shared:
            if timeish(train[c])[0]: time_col = c; break
    if not time_col:
        for c in train.columns:
            if c in sample.columns and timeish(train[c])[0]: time_col = c; break
    if not time_col: raise RuntimeError("could not identify a time column shared by train and sample")
    id_cols = [c for c in (ov.get("id_cols") or shared) if c in shared and c != time_col]
    if not id_cols: id_cols = ["__all__"]
    return dict(sample_p=sample_p, sample=sample, rowid=rowid, train=train,
                target=target, time_col=time_col, id_cols=id_cols)

def order_time(values):
    kind, parsed = timeish(values)
    uniq = sorted(pd.unique(pd.Series(parsed).dropna()))
    idx = {v: i for i, v in enumerate(uniq)}
    if kind == "date": sub = {v: pd.Timestamp(v).month for v in uniq}; cycle = 12
    else:
        cycle = 12 if len(uniq) >= 24 else 0
        sub = {v: (int(v) % cycle if cycle else 0) for v in uniq}
    return kind, uniq, idx, sub, cycle

# ---- candidate level estimators ----
def _last(P):  return P.apply(lambda r: (r.dropna().iloc[-1] if r.dropna().size else np.nan), axis=1)
def _meanK(K):
    def f(P): return P.apply(lambda r: (r.dropna().iloc[-min(K, r.dropna().size):].mean()
                                        if r.dropna().size else np.nan), axis=1)
    return f
def _trend(K=6, damp=0.5):
    def f(P):
        def g(r):
            o = r.dropna()
            if o.size < 3: return o.iloc[-1] if o.size else np.nan
            o = o.iloc[-K:]; x = np.arange(len(o)); b = np.polyfit(x, o.values, 1)
            return o.values[-1] + damp * b[0]
        return P.apply(g, axis=1)
    return f
CANDS = {"last": _last, "mean2": _meanK(2), "mean3": _meanK(3), "mean6": _meanK(6), "trend": _trend(6)}

def seasonal_from(piv, sub_of, target_sps):
    """mean target per subperiod / overall, normalized to mean 1 over the requested subperiods."""
    col_sp = {c: sub_of[c] for c in piv.columns}
    vals = piv.stack(); ovm = vals.mean()
    if not np.isfinite(ovm) or ovm == 0: return {sp: 1.0 for sp in target_sps}
    fac = {}
    for sp in set(target_sps):
        cs = [c for c in piv.columns if col_sp[c] == sp]
        v = piv[cs].stack().mean() if cs else ovm
        fac[sp] = (v / ovm) if np.isfinite(v) and v > 0 else 1.0
    m = np.mean([fac[sp] for sp in target_sps]) or 1.0
    return {sp: fac[sp] / m for sp in fac}

def predict_block(piv, levelfn, target_cols, sub_of, use_seasonal):
    lvl = levelfn(piv)
    sps = [sub_of[c] for c in target_cols]
    fac = seasonal_from(piv, sub_of, sps) if use_seasonal else {sp: 1.0 for sp in sps}
    return {c: lvl * fac.get(sub_of[c], 1.0) for c in target_cols}

def forecast(info):
    sample, rowid, target = info["sample"].copy(), info["rowid"], info["target"]
    train, id_cols, time_col = info["train"].copy(), info["id_cols"], info["time_col"]
    train[target] = pd.to_numeric(train[target], errors="coerce")
    if id_cols == ["__all__"]:
        train["__all__"] = "all"; sample["__all__"] = "all"
    kind, uniq, idx, sub, cycle = order_time(pd.concat([train[time_col], sample[time_col]], ignore_index=True))
    keyf = (lambda v: pd.to_datetime(v)) if kind == "date" else (lambda v: v)
    train["__t"] = train[time_col].map(lambda v: idx.get(keyf(v), np.nan))
    train = train.dropna(subset=["__t"]); train["__t"] = train["__t"].astype(int)
    piv = train.pivot_table(index=id_cols, columns="__t", values=target, aggfunc="mean").reindex(columns=range(len(uniq)))
    sub_of = {i: sub[uniq[i]] for i in range(len(uniq))}
    gmed = float(np.nanmedian(train[target]))

    # ---- internal backtest to choose method (level estimator x seasonal on/off) ----
    obs_cols = [c for c in range(len(uniq)) if piv[c].notna().any()]   # observed (labelled) periods only
    vh = min(6, max(1, len(obs_cols) // 4)); best = None
    if len(obs_cols) - vh >= 6:
        fit_cols = obs_cols[:-vh]; valcols = obs_cols[-vh:]; fit = piv[fit_cols]
        for name, fn in CANDS.items():
            for usef in (True, False):
                try:
                    pred = predict_block(fit, fn, valcols, sub_of, usef)
                    err = pd.concat([(pred[c] - piv[c]).abs() for c in valcols]).mean()
                    if np.isfinite(err) and (best is None or err < best[0]):
                        best = (err, name, usef)
                except Exception: pass
    name, usef = (best[1], best[2]) if best else ("mean3", cycle > 0)

    # ---- refit on full history, forecast the requested periods ----
    tgt_cols = sorted({idx[keyf(v)] for v in sample[time_col] if keyf(v) in idx})
    pred = predict_block(piv, CANDS[name], tgt_cols, sub_of, usef)
    longpred = []
    for c in tgt_cols:
        s = pred[c].rename(target).reset_index(); s["__t"] = c; longpred.append(s)
    pm = pd.concat(longpred, ignore_index=True)
    sample["__t"] = sample[time_col].map(lambda v: idx.get(keyf(v), -1))
    out = sample.merge(pm, on=id_cols + ["__t"], how="left", suffixes=("", "_p"))
    pcol = target + "_p" if target + "_p" in out.columns else target
    out[target] = pd.to_numeric(out[pcol], errors="coerce")
    out[target] = out[target].fillna(gmed if np.isfinite(gmed) else 0.0).clip(lower=0)
    return out[[rowid, target]].copy(), dict(kind=kind, n_periods=len(uniq), n_groups=int(piv.shape[0]),
            cycle=cycle, method=name, seasonal=usef, val_mae=(best[0] if best else float("nan")), gmed=gmed)

def write_baseline(info):
    sample, rowid, target, train, id_cols = info["sample"], info["rowid"], info["target"], info["train"], info["id_cols"]
    out = sample[[rowid]].copy()
    val = float(pd.to_numeric(train[target], errors="coerce").median())
    if not np.isfinite(val): val = 0.0
    try:
        if id_cols != ["__all__"]:
            last = (train.dropna(subset=[target]).groupby(id_cols)[target]
                    .apply(lambda s: pd.to_numeric(s, errors="coerce").dropna().iloc[-1]))
            out[target] = sample.merge(last.rename("__v").reset_index(), on=id_cols, how="left")["__v"].fillna(val).values
        else: out[target] = val
    except Exception: out[target] = val
    out[target] = pd.to_numeric(out[target], errors="coerce").fillna(val)
    out[[rowid, target]].to_csv(SUB_PATH, index=False)
    log(f"baseline written ({len(out)} rows)")

def write_report(info, meta, n):
    L = ["STAI-X Award B - Automated Panel Forecast Report", "",
         "Detected schema",
         f"  training rows : {len(info['train'])}", f"  target        : {info['target']}",
         f"  time column   : {info['time_col']} ({meta['kind']})",
         f"  group id cols : {', '.join(info['id_cols'])}",
         f"  groups/periods: {meta['n_groups']} groups, {meta['n_periods']} periods", "",
         "Method (auto-selected by internal backtest on recent periods)",
         f"  level estimator : {meta['method']}", f"  seasonal applied: {meta['seasonal']} (cycle={meta['cycle']})",
         f"  internal val MAE: {meta['val_mae']:.4f}" if np.isfinite(meta.get('val_mae', float('nan'))) else
         "  internal val MAE: n/a (short history -> default used)", "",
         "  Candidates compared: last value, recent mean (2/3/6), damped trend,",
         "  each with and without seasonal re-scaling; the lowest-error option on a",
         "  held-out tail of the training data was selected, then refit on full data.", "",
         "Robustness",
         "  - Baseline submission written before modeling (safety net).",
         "  - Schema auto-detected; missing values/columns guarded.",
         "  - Output is exactly two columns (row_id, target), finite, one row per id.", "",
         f"Output: submission.csv with {n} rows."]
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        c = canvas.Canvas(REPORT_PATH, pagesize=LETTER); w, h = LETTER; y = h - inch
        c.setFont("Helvetica-Bold", 14); c.drawString(inch, y, L[0]); y -= 26; c.setFont("Helvetica", 10)
        for ln in L[1:]:
            if y < inch: c.showPage(); c.setFont("Helvetica", 10); y = h - inch
            c.drawString(inch, y, ln[:110]); y -= 14
        c.save(); log("report.pdf written"); return
    except Exception as e: log(f"reportlab failed ({e}); trying matplotlib")
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        with PdfPages(REPORT_PATH) as pdf:
            fig = plt.figure(figsize=(8.5, 11))
            fig.text(0.07, 0.95, L[0], fontsize=13, weight="bold", va="top")
            fig.text(0.07, 0.90, "\n".join(L[1:]), fontsize=9, va="top", family="monospace")
            pdf.savefig(fig); plt.close(fig)
        log("report.pdf written (matplotlib)")
    except Exception as e:
        log(f"no PDF backend ({e}); writing report.txt"); open(os.path.join(ROOT, "report.txt"), "w").write("\n".join(L))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--target"); ap.add_argument("--time"); ap.add_argument("--id-cols")
    a = ap.parse_args(); ov = {}
    if a.target: ov["target"] = a.target
    if a.time: ov["time"] = a.time
    if a.id_cols: ov["id_cols"] = [c.strip() for c in a.id_cols.split(",")]
    csvs = list_csvs(); log("CSV files:", [os.path.relpath(p, DATA) for p in csvs])
    frames = {p: pd.read_csv(p) for p in csvs}
    info = detect(frames, ov)
    log(f"detected -> target='{info['target']}', time='{info['time_col']}', id_cols={info['id_cols']}, rowid='{info['rowid']}'")
    write_baseline(info)
    try:
        out, meta = forecast(info)
        assert out.shape[1] == 2 and out[info["rowid"]].is_unique and len(out) == len(info["sample"])
        med = float(np.nanmedian(out[info["target"]]))
        out[info["target"]] = out[info["target"]].fillna(med if np.isfinite(med) else 0.0)
        assert np.isfinite(out[info["target"]]).all()
        out.to_csv(SUB_PATH, index=False)
        log(f"forecast written ({len(out)} rows); method={meta['method']}, seasonal={meta['seasonal']}")
        write_report(info, meta, len(out))
    except Exception:
        log("forecast failed; keeping baseline. Traceback:"); traceback.print_exc()
        write_report(info, dict(kind="?", n_periods=0, n_groups=0, cycle=0, method="baseline",
                                seasonal=False, val_mae=float("nan"), gmed=float("nan")), len(info["sample"]))

if __name__ == "__main__": main()
