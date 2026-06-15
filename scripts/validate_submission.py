from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def find_description_text(data_dir: Path) -> str:
    texts = []
    for path in sorted(data_dir.rglob("*.md")):
        name = path.name.lower()
        if "description" in name or name in {"readme.md", "data.md"}:
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(texts)


def find_sample_submission(data_dir: Path) -> Path | None:
    candidates = []
    for path in data_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".csv", ".tsv", ".txt"}:
            if "sample" in path.name.lower() and "submission" in path.name.lower():
                candidates.append(path)
    return sorted(candidates)[0] if candidates else None


def read_csv_flexible(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def clean_token(token: str) -> str:
    return token.strip().strip("`'\"* <>{}[]().,:;")


def infer_target_from_description(description: str) -> str | None:
    patterns = [
        r"predict\s+`?([A-Za-z_][\w.-]*)`?",
        r"target column(?: name)?\s*(?:is|:)\s*`?([A-Za-z_][\w.-]*)`?",
        r"prediction target\s*(?:is|:)\s*`?([A-Za-z_][\w.-]*)`?",
        r"fill\s+`?([A-Za-z_][\w.-]*)`?",
        r"columns?\s*(?:are|:)\s*`?row_id`?\s*,\s*`?([A-Za-z_][\w.-]*)`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            token = clean_token(match.group(1))
            if token.lower() not in {"the", "this", "every", "all"}:
                return token
    return None


def infer_target_from_sample(sample: pd.DataFrame) -> str | None:
    if "row_id" not in sample.columns:
        return None
    non_id = [c for c in sample.columns if c != "row_id"]
    numeric = []
    for col in non_id:
        values = pd.to_numeric(sample[col], errors="coerce")
        if values.notna().mean() >= 0.8:
            numeric.append(col)
    zero_like = [c for c in numeric if pd.to_numeric(sample[c], errors="coerce").fillna(0).abs().sum() == 0]
    if zero_like:
        return zero_like[-1]
    return numeric[-1] if numeric else (non_id[-1] if non_id else None)


def validate_submission(data_dir: Path, submission_path: Path) -> tuple[bool, dict[str, Any]]:
    result: dict[str, Any] = {"ok": False, "errors": [], "warnings": []}
    if not submission_path.exists():
        result["errors"].append(f"Missing submission file: {submission_path}")
        return False, result

    try:
        submission = read_csv_flexible(submission_path)
    except Exception as exc:
        result["errors"].append(f"Could not read submission CSV: {exc}")
        return False, result

    description = find_description_text(data_dir)
    sample_path = find_sample_submission(data_dir)
    sample = read_csv_flexible(sample_path) if sample_path else None
    target = infer_target_from_description(description)
    if target is None and sample is not None:
        target = infer_target_from_sample(sample)
    if target is None:
        result["errors"].append("Could not infer target column from description or sample submission.")
        return False, result

    expected_columns = ["row_id", target]
    result["expected_columns"] = expected_columns
    result["actual_columns"] = list(submission.columns)
    if list(submission.columns) != expected_columns:
        result["errors"].append(f"Submission columns must be exactly {expected_columns}, got {list(submission.columns)}.")

    if "row_id" not in submission.columns:
        result["errors"].append("Submission is missing row_id.")
    elif submission["row_id"].duplicated().any():
        result["errors"].append("Submission row_id contains duplicates.")

    if sample is not None and "row_id" in sample.columns and "row_id" in submission.columns:
        expected_ids = sample["row_id"].tolist()
        actual_ids = submission["row_id"].tolist()
        if set(actual_ids) != set(expected_ids):
            missing = sorted(set(expected_ids) - set(actual_ids))[:10]
            extra = sorted(set(actual_ids) - set(expected_ids))[:10]
            result["errors"].append(f"row_id set mismatch. Missing examples: {missing}; extra examples: {extra}.")
        if len(actual_ids) != len(expected_ids):
            result["errors"].append(f"Expected {len(expected_ids)} rows, got {len(actual_ids)}.")
        elif actual_ids != expected_ids:
            result["warnings"].append("row_id order differs from sample_submission.csv.")

    if target in submission.columns:
        values = pd.to_numeric(submission[target], errors="coerce")
        if values.isna().any():
            result["errors"].append(f"Target column {target} contains nonnumeric or missing predictions.")
        elif not np.isfinite(values.to_numpy(dtype=float)).all():
            result["errors"].append(f"Target column {target} contains non-finite predictions.")
        result["prediction_summary"] = {
            "min": float(values.min()) if len(values) else None,
            "mean": float(values.mean()) if len(values) else None,
            "max": float(values.max()) if len(values) else None,
        }

    result["sample_submission"] = str(sample_path) if sample_path else None
    result["ok"] = not result["errors"]
    return result["ok"], result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Award B submission.csv schema and row IDs.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--submission", default="submission.csv")
    parser.add_argument("--json-out", default="analysis_outputs/validation.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, result = validate_submission(Path(args.data_dir), Path(args.submission))
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
