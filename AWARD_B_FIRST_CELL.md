## Award B Submission

### Team info
| Legal name | Affiliation | Institutional email | Kaggle username |
|---|---|---|---|
| [Lingxi — your legal name] | [NUS / Duke-NUS] | [your institutional email] | [your kaggle username] |
| [Yao — legal name] | [affiliation] | [email] | [kaggle username] |
| [Minhao — legal name] | [affiliation] | [email] | [kaggle username] |
| [member 4 — legal name] | [affiliation] | [email] | [kaggle username] |

**Registered team name:** FQGroup

**GitHub repository:** https://github.com/<your-account>/<your-repo>  (commit tagged `award-b-submission`)

### Agent Design and Architecture
| Component | What it does |
|---|---|
| Brain / LLM | `claude-sonnet-4.6` (medium effort) — single orchestrator that reads `data/DATA_DESCRIPTION.md`, runs the pipeline, validates the outputs, and writes the report |
| Memory | Persistent guidance in `CLAUDE.md`; per-run scratch state in the working directory; no cross-run memory |
| Planning | (1) read data + infer schema, (2) write a safety-net baseline submission, (3) run the adaptive forecast, (4) validate the submission schema, (5) generate `report.pdf` |
| Action | `panel-forecast` skill and `data-analyst` sub-agent under `.claude/`; runs `pipeline.py`; standard Claude Code tools (Read / Write / Edit / Bash) |
| Execution | `claude --dangerously-skip-permissions` from the repo root; within the 2-hour / 1M-token caps; no local GPU |
| Observation | Checks the pipeline's logs and the auto-detected schema against `data/DATA_DESCRIPTION.md`; validates `submission.csv` (two columns, row count, finite) before finishing; summarizes in `report.pdf` |
