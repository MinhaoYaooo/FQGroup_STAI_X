# STAI-X Challenge 2026 — Award B: Autonomous Panel-Forecast Agent (FQGroup)

A general-purpose Claude Code agent that, given an unseen panel dataset placed in `data/`
(with a `data/DATA_DESCRIPTION.md`), autonomously produces `submission.csv` and
`report.pdf` at the repository root.

## How it is run (evaluation)
From the repo root, with the dataset already in `data/`:

```bash
claude --dangerously-skip-permissions
# then a single prompt:
# > Do the data analysis
```

The agent reads `CLAUDE.md`, follows the procedure there, and uses the `panel-forecast`
skill, which runs `pipeline.py`.

## Pipeline design
`pipeline.py` is a domain-agnostic panel forecaster:

1. **Schema auto-detection** — finds the training file, the sample/validation file,
   `row_id`, the target, the id/group columns, and the time column from the CSVs in
   `data/` (all overridable via CLI flags).
2. **Safety-net baseline** — writes a valid `submission.csv` immediately (per-group last
   value / global median) *before* any modeling, so a valid file always exists.
3. **Adaptive forecast** — per-group level (last value / recent mean / damped trend) ×
   seasonal factor; the level estimator and whether to use seasonality are selected by an
   **internal backtest on the most recent training periods**, so the method adapts to the
   data (trending vs level-dominated, seasonal vs not).
4. **Report** — `report.pdf` summarizing the detected schema, the selected method, and the
   internal validation result.

Robustness: missing values and columns are guarded; the output is always exactly two
columns (`row_id`, target), finite, with one row per validation `row_id`.

## Repository structure
```
.
├── CLAUDE.md                          # agent playbook (read first)
├── pipeline.py                        # the forecasting backend
├── README.md                          # this file
├── data/                              # empty; the evaluator populates it
│   └── .gitkeep
└── .claude/
    ├── agents/
    │   └── data-analyst.md            # sub-agent that runs + validates the pipeline
    └── skills/
        └── panel-forecast/
            └── SKILL.md               # skill describing how to use pipeline.py
```

## Reproduce locally
Put a panel dataset into `data/` — a training CSV, an optional covariates CSV, a
`sample_submission.csv` with a `row_id` column and the target column, and a
`data/DATA_DESCRIPTION.md` — then run:

```bash
python pipeline.py
```

It writes `submission.csv` and `report.pdf` to the repo root.
