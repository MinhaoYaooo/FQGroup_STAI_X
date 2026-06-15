---
name: award-b-data-analysis
description: Explore the held-out data, write dataset-specific analysis code, and create submission.csv plus report.pdf for STAIX Award B.
---

# Award B Adaptive Data Analysis Skill

Use this skill whenever the user asks to analyze the data, do the data analysis, make predictions, create a submission, or prepare the Award B held-out artifacts.

## Critical Behavior

Do not ask what analysis to run. Do not run a fixed universal predictor. First inspect the files in `data/`, then write code tailored to the discovered schema.

## Required Steps

1. Profile the data recursively:

```bash
python scripts/profile_data.py --data-dir data --out analysis_outputs/data_profile.json --markdown analysis_outputs/data_profile.md --image-manifest analysis_outputs/image_manifest.csv
```

Use `py` if `python` is unavailable.

2. Read the data description and profile. Determine the target, sample submission, training labels, validation rows, covariates, keys, and optional sidecar data. If images exist, inspect `analysis_outputs/image_manifest.csv` and the `image_join_hints` in `analysis_outputs/data_profile.json`.

3. Write a custom script under `analysis_outputs/`, for example:

```text
analysis_outputs/analyze_and_predict.py
```

That script must read from `data/` and write the root-level `submission.csv`. It should also write `analysis_outputs/report.md` or directly create `report.pdf`.

4. Run the custom script. If it fails, debug and rerun.

5. Validate the submission:

```bash
python scripts/validate_submission.py --data-dir data --submission submission.csv --json-out analysis_outputs/validation.json
```

6. Create `report.pdf`. If the custom script wrote Markdown, use:

```bash
python scripts/report_utils.py --markdown analysis_outputs/report.md --out report.pdf
```

7. Continue iterating until `submission.csv` validates and `report.pdf` exists.

## Modeling Guidance

Build the analysis around the discovered task. Prefer simple, robust models and validation designs over brittle assumptions. If the data are panel-like, use time-aware or group-aware validation when possible. If the sample submission contains prediction rows, use it as the authoritative output frame.

For multimodal data, do not assume any single image filename pattern. First look for an explicit image manifest or path column. If none exists, use the generated image manifest to compare filename stems, path tokens, directories, and image counts with table values. Join image features only when the mapping is justified by the description or strong token/value overlap. If row-level joins are ambiguous, either skip the images or use only safe aggregate features that cannot leak labels.

For model selection, approximate the official block-averaged MAE when a block or group variable can be inferred:

$$\mathrm{MAE}_{\mathrm{block}}=\frac{1}{|\mathcal{B}|}\sum_{b\in\mathcal{B}}\frac{1}{|b|}\sum_{i\in b}\left|y_i-\hat{y}_i\right|.$$

## Output Contract

The task is incomplete unless the repository root contains:

- `submission.csv`
- `report.pdf`

The final response should mention both artifacts and whether validation passed.
