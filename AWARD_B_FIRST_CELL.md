## Award B Submission

### Team info
| Legal name | Affiliation | Institutional email | Kaggle username |
|---|---|---|---|
| Lingxi Wang | Duke-NUS Medical School | e1538207@u.nus.edu | Lingxi wang_2003 |
| Yao Pei | Duke-NUS Medical School | scpeiyao@gmail.com | scpeiyao |
| Minhao Yao | Duke-NUS Medical School | minhaoyaoooo@gmail.com | YAO MINHAO |
| Qiao Fan | Duke-NUS Medical School | gmsfq@nus.edu.sg | Qiao FAN |

**Registered team name:** FQGroup

**GitHub repository:** [https://github.com/MinhaoYaooo/FQGroup_STAI_X](https://github.com/MinhaoYaooo/FQGroup_STAI_X)  (commit tagged `award-b-submission`)

### Agent Design and Architecture

| Component | What it does |
|---|---|
| Brain / LLM | `claude-sonnet-4.6` (medium effort) — single orchestrator that first explores the held-out `data/` folder, reads any data description file such as `DATA_DESCRIPTION.md` or `Data_Description.md`, then writes dataset-specific analysis code and produces the required artifacts |
| Memory | Persistent guidance in `CLAUDE.md`; task-specific workflow guidance in `.claude/skills/award-b-data-analysis/SKILL.md`; per-run scratch state in `analysis_outputs/`; no cross-run memory |
| Planning | (1) recursively profile `data/`, (2) infer training labels, validation rows, target, keys, covariates, sample submission, and sidecar data, (3) write a custom script such as `analysis_outputs/analyze_and_predict.py`, (4) train and validate models suited to the discovered schema, (5) write `submission.csv`, (6) validate schema and row IDs, (7) generate `report.pdf` |
| Action | Adaptive `award-b-data-analysis` skill under `.claude/`; helper utilities in `scripts/profile_data.py`, `scripts/validate_submission.py`, and `scripts/report_utils.py`; standard Claude Code tools (Read / Write / Edit / Bash) |
| Execution | `claude --dangerously-skip-permissions` from the repo root; within the 2-hour / 1M-token caps; no assumed local GPU; no internet browsing or model downloads |
| Observation | Uses `analysis_outputs/data_profile.json`, `analysis_outputs/data_profile.md`, optional `analysis_outputs/image_manifest.csv`, script logs, validation JSON, and the original data description to check assumptions; validates `submission.csv` for exact columns, `row_id` coverage, row count, and finite numeric predictions before finishing; summarizes methods and diagnostics in `report.pdf` |
| Multimodal Handling | Recursively detects image sidecars and writes an image manifest with paths, directory roles, filename/path tokens, dimensions, and simple pixel statistics when available; joins image features only when the mapping is justified by the description, explicit manifest/path columns, or strong token/value overlap; otherwise skips images or uses only safe aggregate features |
