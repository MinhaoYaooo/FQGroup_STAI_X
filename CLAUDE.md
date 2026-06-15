# Award B Agent — Autonomous Panel-Forecast Pipeline

You are an autonomous data-analysis agent. When the user says **"Do the data analysis"**,
carry out the procedure below end-to-end without asking questions, and finish within the
**2-hour / 1,000,000-token** budget. No human will help after the first prompt.

## Goal
Produce two files at the **repository root**:

1. `submission.csv` — **exactly two columns**: `row_id` and the target column named in
   `data/DATA_DESCRIPTION.md`. One row per `row_id` in the validation / sample-submission
   file, every value finite.
2. `report.pdf` — a short description of the data, the method, and the validation.

A missing or schema-mismatched `submission.csv` receives the worst score, so
**guaranteeing a valid `submission.csv` is the single highest priority** — everything
else is secondary.

## Procedure
1. **Read `data/DATA_DESCRIPTION.md`.** Identify: the training file, the validation /
   sample-submission file, the `row_id` column, the target column name, the group/id
   columns, and the time column.
2. **Run the pipeline:** `python pipeline.py`
   - It auto-detects the schema, writes a **baseline `submission.csv` immediately**
     (safety net), then replaces it with an adaptive forecast, and writes `report.pdf`.
   - It prints the schema it detected.
3. **Check the detected schema** against `data/DATA_DESCRIPTION.md`. If the target, time,
   or id columns are wrong, re-run with overrides:
   `python pipeline.py --target <TARGET> --time <TIMECOL> --id-cols <col1,col2>`
4. **Validate the output explicitly:**
   - `submission.csv` exists at the repo root.
   - It has exactly two columns: `row_id` and the target name from `DATA_DESCRIPTION.md`.
   - Its row count equals the number of rows in the validation / sample file.
   - All target values are finite (no NaN / inf).
   - `report.pdf` exists.
5. **If `pipeline.py` cannot produce a valid file, do not give up.** Write a minimal valid
   `submission.csv` yourself: for each validation row, set the target to that group's last
   observed value in the training file (or the global mean/median if the group is unknown),
   with exactly the two required columns. Then write a brief `report.pdf` (or `report.txt`
   if no PDF library is available).

## What the pipeline does
Between-group level differences dominate panel-forecast variance, so `pipeline.py`
estimates each group's level from its most recent periods and re-applies the seasonal
shape. It chooses among several level estimators (last value, recent mean, damped trend)
and whether to use seasonality by an **internal backtest on the most recent training
periods**, so it adapts to trending vs level-dominated and seasonal vs non-seasonal data.

## Constraints
- Use only `pandas`, `numpy`, and (for the PDF) `reportlab` or `matplotlib` — all expected
  to be present. Do not depend on a GPU or large downloads.
- Be decisive: glance at the data, run the pipeline, validate, write the report. Do not
  spend the budget exploring. **Stop as soon as both output files are valid.**
