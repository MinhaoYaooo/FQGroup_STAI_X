---
name: panel-forecast
description: Forecast a panel / longitudinal time-series dataset (multiple groups observed over time) to fill a sample_submission. Use whenever the task is to predict a numeric target for future or held-out periods of a multi-group time series, given a training panel plus a sample/validation file keyed by row_id. Produces submission.csv (row_id, target) and report.pdf at the repo root.
---

# Panel forecasting

Use this skill for any task that asks you to predict a numeric target for a **panel
dataset** — multiple groups (e.g. states, stores, products) each observed over time —
and to fill a `sample_submission` keyed by `row_id`.

## How to run
From the repo root:

```bash
python pipeline.py
```

This:
- Auto-detects the training file, the validation/sample file, `row_id`, the target, the
  id/group columns, and the time column from the CSVs in `data/`.
- Writes a **baseline `submission.csv` first** (safety net), then replaces it with an
  adaptive forecast.
- Writes `report.pdf`.

If the auto-detected schema disagrees with `data/DATA_DESCRIPTION.md`, override it:

```bash
python pipeline.py --target <TARGET_COL> --time <TIME_COL> --id-cols <id1,id2>
```

## Method
Per-group level (last value / recent mean / damped trend) × seasonal factor. The level
estimator and whether to apply seasonality are chosen by an **internal backtest on the
most recent training periods**, so the method adapts to the dataset. Robust to missing
values, missing columns, short histories, and trending vs level-dominated series.

## Output contract
- `submission.csv` at the repo root: exactly two columns — `row_id` and the target name
  from `data/DATA_DESCRIPTION.md` — one row per validation `row_id`, all finite.
- `report.pdf` at the repo root: data summary, method, and the selected configuration.

After running, confirm both files exist and that `submission.csv` matches the required
schema and row count before finishing.
