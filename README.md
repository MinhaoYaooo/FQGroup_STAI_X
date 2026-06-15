# STAIX Award B Adaptive Claude Agent

This repository is a Claude Code submission scaffold for the Award B held-out evaluation. Organizers place an unknown dataset into `data/`, open the repo in Claude Code, and prompt:

```text
Do the data analysis.
```

The repo intentionally avoids a fixed universal prediction pipeline. Claude is instructed to explore the hidden data first, then write a dataset-specific analysis script during the run.

## Structure

```text
your-repo/
|-- data/
|-- CLAUDE.md
|-- .claude/
|   `-- skills/
|       `-- award-b-data-analysis/
|           `-- SKILL.md
|-- scripts/
|   |-- profile_data.py
|   |-- validate_submission.py
|   |-- report_utils.py
|   `-- smoke_test.py
|-- README.md
`-- requirements.txt
```

## Expected Evaluation Behavior

When Claude receives `Do the data analysis`, it should:

1. recursively profile `data/`,
2. read the data description,
3. identify the target and required submission schema,
4. write custom analysis code under `analysis_outputs/`,
5. train and validate models suited to the discovered data,
6. write `submission.csv` to the repo root,
7. write `report.pdf` to the repo root,
8. validate the submission schema and row IDs.

## Helper Commands

Profile the hidden data:

```bash
python scripts/profile_data.py --data-dir data --out analysis_outputs/data_profile.json --markdown analysis_outputs/data_profile.md --image-manifest analysis_outputs/image_manifest.csv
```

When images are present, this also writes `analysis_outputs/image_manifest.csv` with path tokens, directory hints, dimensions, and simple pixel statistics when Pillow is available.

Validate the final submission:

```bash
python scripts/validate_submission.py --data-dir data --submission submission.csv --json-out analysis_outputs/validation.json
```

Create a PDF from a Markdown report:

```bash
python scripts/report_utils.py --markdown analysis_outputs/report.md --out report.pdf
```

On Windows, if `python` is not on PATH, try `py`.

## Local Smoke Test

```bash
python scripts/smoke_test.py
```

The smoke test verifies the helper utilities. It does not run a fixed prediction pipeline.

## Submission Tag

Before the deadline, tag the intended commit:

```bash
git tag -f award-b-submission
git push origin award-b-submission --force
```
