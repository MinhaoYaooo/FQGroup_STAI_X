# Award B Adaptive Claude Agent

## Mission

When the user says "Do the data analysis", produce the required held-out evaluation artifacts without asking follow-up questions:

- `submission.csv` in the repository root.
- `report.pdf` in the repository root.

This repository intentionally does not contain a fixed prediction pipeline. First inspect the files placed in `data/`, then write and run dataset-specific analysis code.

## Non-Negotiable Rules

- Do not browse the internet.
- Do not ask the user what to do next.
- Treat the data description in `data/` as the source of truth, including files named like `DATA_DESCRIPTION.md`, `Data_Description.md`, or similar.
- Preserve the required submission schema exactly.
- Use every `row_id` required by the sample submission or data description, with no extra rows.
- Keep all generated work in `analysis_outputs/` except the two required root artifacts.
- Iterate until both `submission.csv` and `report.pdf` exist and validation passes.

## Required Adaptive Workflow

1. Explore the data layout recursively:

```bash
python scripts/profile_data.py --data-dir data --out analysis_outputs/data_profile.json --markdown analysis_outputs/data_profile.md --image-manifest analysis_outputs/image_manifest.csv
```

If `python` is unavailable, try `py`.

2. Read the generated profile and the original data description. Identify:

- training labels,
- validation or test rows,
- covariate tables,
- sample submission template,
- target column,
- required output columns,
- optional sidecar data such as text, images, or nested folders.
- image manifests, path tokens, and possible table-column join hints when images are present.

3. Write a fresh dataset-specific script, usually:

```text
analysis_outputs/analyze_and_predict.py
```

The script should start from the raw `data/` files and create `submission.csv` and an analysis summary file such as `analysis_outputs/report.md`.

4. Choose modeling methods that match the discovered data. Examples:

- Join label and covariate panels using the discovered keys.
- Use the sample submission as the prediction frame when present.
- Include categorical variables such as geography, category, or group identifiers.
- Use date or period structure when it is available.
- Use text features when text columns are present.
- Use `analysis_outputs/image_manifest.csv` for image sidecars. Do not assume a fixed filename convention. Infer image joins from the data description, explicit manifest files, directory roles, filename/path tokens, table-value overlaps, or row-level references. If exact row-level joining is unclear, consider safe aggregate image features by folder, split, group, or period only when they do not leak validation labels.
- Extract simple image statistics from image sidecars when they can be joined or aggregated safely.
- Train category-specific models when the target behavior differs by category.
- Compare candidate models with a local validation split that respects time, group, or block structure when possible.

5. Optimize for the block-averaged MAE metric when a compatible validation proxy can be built:

$$
\mathrm{MAE}_{\mathrm{block}}
=
\frac{1}{|\mathcal{B}|}
\sum_{b\in\mathcal{B}}
\frac{1}{|b|}
\sum_{i\in b}
\left|y_i-\hat{y}_i\right|.
$$

6. Validate the final submission:

```bash
python scripts/validate_submission.py --data-dir data --submission submission.csv --json-out analysis_outputs/validation.json
```

If validation fails, inspect the error, fix the dataset-specific script, rerun, and validate again.

7. Generate `report.pdf`. The custom analysis script may create it directly, or it may write `analysis_outputs/report.md` and then run:

```bash
python scripts/report_utils.py --markdown analysis_outputs/report.md --out report.pdf
```

8. Before the final response, verify:

```bash
python scripts/validate_submission.py --data-dir data --submission submission.csv --json-out analysis_outputs/validation.json
```

Also confirm `report.pdf` exists and is non-empty.

## Final Response

Keep the final response brief. State that `submission.csv` and `report.pdf` were created, mention the selected modeling approach, and mention whether validation passed.

## Repository Layout

- `data/`: populated by organizers during evaluation.
- `.claude/skills/award-b-data-analysis/SKILL.md`: project skill for this adaptive workflow.
- `scripts/profile_data.py`: recursive data profiler.
- `scripts/validate_submission.py`: schema and `row_id` validator.
- `scripts/report_utils.py`: helper for creating `report.pdf` from Markdown.
- `analysis_outputs/`: generated exploratory code, profiles, diagnostics, and intermediate reports.
