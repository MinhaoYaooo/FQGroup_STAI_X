from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TABULAR_EXTENSIONS = {".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
DESCRIPTION_PATTERNS = (
    "data_description.md",
    "data-description.md",
    "datadescription.md",
    "description.md",
    "readme.md",
)


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def safe_json(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def find_description_files(data_dir: Path) -> list[Path]:
    matches = []
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower().replace("_", "-")
        compact = path.name.lower().replace("_", "").replace("-", "")
        if name in DESCRIPTION_PATTERNS or compact in DESCRIPTION_PATTERNS:
            matches.append(path)
        elif path.suffix.lower() == ".md" and "description" in path.name.lower():
            matches.append(path)
    return sorted(set(matches))


def read_description(data_dir: Path) -> dict[str, Any]:
    files = find_description_files(data_dir)
    descriptions = []
    for path in files:
        try:
            descriptions.append(
                {
                    "path": rel(path, data_dir),
                    "text": path.read_text(encoding="utf-8", errors="ignore"),
                }
            )
        except Exception as exc:
            descriptions.append({"path": rel(path, data_dir), "error": str(exc)})
    return {"files": descriptions}


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            df = pd.read_csv(path)
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin-1")
        if df.shape[1] == 1:
            try:
                retry = pd.read_csv(path, sep=None, engine="python")
                if retry.shape[1] > 1:
                    df = retry
            except Exception:
                pass
        return df
    if suffix in {".tsv", ".txt"}:
        try:
            return pd.read_csv(path, sep="\t")
        except Exception:
            return pd.read_csv(path, sep=None, engine="python")
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported table extension: {path.suffix}")


def sample_values(series: pd.Series, n: int = 5) -> list[Any]:
    values = series.dropna().unique()[:n]
    return [safe_json(v) for v in values]


def summarize_column(series: pd.Series) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "dtype": str(series.dtype),
        "missing_count": int(series.isna().sum()),
        "missing_rate": float(series.isna().mean()) if len(series) else 0.0,
        "unique_count": int(series.nunique(dropna=True)),
        "sample_values": sample_values(series),
    }
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() >= 0.8 and numeric.notna().sum() > 0:
        summary["numeric"] = {
            "mean": safe_json(numeric.mean()),
            "std": safe_json(numeric.std()),
            "min": safe_json(numeric.min()),
            "median": safe_json(numeric.median()),
            "max": safe_json(numeric.max()),
        }
    elif pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        text = series.fillna("").astype(str)
        summary["text"] = {
            "mean_length": safe_json(text.str.len().mean()),
            "max_length": safe_json(text.str.len().max()),
            "nonempty_rate": safe_json((text.str.len() > 0).mean()),
        }
        top = text[text != ""].value_counts().head(5)
        summary["top_values"] = {str(k): int(v) for k, v in top.items()}
    return summary


def infer_table_role(path: Path, columns: list[str]) -> list[str]:
    text = (path.as_posix() + " " + " ".join(columns)).lower()
    roles = []
    if "sample_submission" in text or "submission" in text:
        roles.append("sample_submission")
    if re.search(r"(^|/|\\)train(ing)?(/|\\|_|-|$)", text) or "target" in text or "label" in text:
        roles.append("possible_training")
    if re.search(r"(^|/|\\)(val|valid|validation|test|holdout)(/|\\|_|-|$)", text):
        roles.append("possible_validation")
    if "covariate" in text or "feature" in text or "panel" in text:
        roles.append("possible_covariates")
    return roles or ["unclassified"]


def summarize_table(path: Path, data_dir: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path, data_dir), "extension": path.suffix.lower()}
    try:
        df = read_table(path)
    except Exception as exc:
        item["error"] = str(exc)
        return item
    df.columns = [str(c).strip() for c in df.columns]
    item["rows"] = int(df.shape[0])
    item["columns"] = list(df.columns)
    item["roles"] = infer_table_role(path, item["columns"])
    item["column_summaries"] = {col: summarize_column(df[col]) for col in df.columns}
    item["duplicate_rows"] = int(df.duplicated().sum())
    id_like = [c for c in df.columns if c.lower() == "row_id" or c.lower().endswith("_id") or c.lower() in {"id", "key"}]
    item["id_like_columns"] = id_like
    return item


def summarize_images(paths: list[Path], data_dir: Path) -> dict[str, Any]:
    groups: dict[str, Any] = {
        "count": len(paths),
        "extensions": {},
        "directories": {},
        "examples": [rel(p, data_dir) for p in paths[:12]],
    }
    for path in paths:
        groups["extensions"][path.suffix.lower()] = groups["extensions"].get(path.suffix.lower(), 0) + 1
        directory = rel(path.parent, data_dir)
        groups["directories"][directory] = groups["directories"].get(directory, 0) + 1
    return groups


def tokenize_text(text: str) -> list[str]:
    tokens = re.split(r"[^A-Za-z0-9]+", str(text).lower())
    return [token for token in tokens if token]


def infer_image_role(path: Path) -> str:
    text = path.as_posix().lower()
    if re.search(r"(^|/|\\)train(ing)?(/|\\|_|-|$)", text):
        return "possible_training_image"
    if re.search(r"(^|/|\\)(val|valid|validation|test|holdout)(/|\\|_|-|$)", text):
        return "possible_validation_image"
    return "unclassified_image"


def extract_image_stats(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        return {"stats_error": f"Pillow unavailable: {exc}"}

    try:
        with Image.open(path) as image:
            original_mode = image.mode
            width, height = image.size
            rgba = image.convert("RGBA")
            arr = np.asarray(rgba, dtype=np.float32) / 255.0
    except Exception as exc:
        return {"stats_error": f"Could not read image: {exc}"}

    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    luminance = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    nontransparent = alpha > 0.05
    active = luminance[nontransparent] if nontransparent.any() else luminance.reshape(-1)
    return {
        "width": int(width),
        "height": int(height),
        "mode": original_mode,
        "aspect_ratio": safe_json(width / height if height else None),
        "alpha_nonzero_fraction": safe_json(nontransparent.mean()),
        "luminance_mean": safe_json(active.mean()),
        "luminance_std": safe_json(active.std()),
        "luminance_p10": safe_json(np.quantile(active, 0.10)),
        "luminance_p50": safe_json(np.quantile(active, 0.50)),
        "luminance_p90": safe_json(np.quantile(active, 0.90)),
        "dark_fraction": safe_json((active < 0.20).mean()),
        "bright_fraction": safe_json((active > 0.80).mean()),
        "red_mean": safe_json(rgb[:, :, 0][nontransparent].mean() if nontransparent.any() else rgb[:, :, 0].mean()),
        "green_mean": safe_json(rgb[:, :, 1][nontransparent].mean() if nontransparent.any() else rgb[:, :, 1].mean()),
        "blue_mean": safe_json(rgb[:, :, 2][nontransparent].mean() if nontransparent.any() else rgb[:, :, 2].mean()),
        "red_std": safe_json(rgb[:, :, 0][nontransparent].std() if nontransparent.any() else rgb[:, :, 0].std()),
        "green_std": safe_json(rgb[:, :, 1][nontransparent].std() if nontransparent.any() else rgb[:, :, 1].std()),
        "blue_std": safe_json(rgb[:, :, 2][nontransparent].std() if nontransparent.any() else rgb[:, :, 2].std()),
    }


def image_manifest_record(path: Path, data_dir: Path, include_stats: bool) -> dict[str, Any]:
    relative = rel(path, data_dir)
    parts = list(path.relative_to(data_dir).parts) if path.is_relative_to(data_dir) else list(path.parts)
    parent_parts = parts[:-1]
    stem_tokens = tokenize_text(path.stem)
    parent_tokens = []
    for part in parent_parts:
        parent_tokens.extend(tokenize_text(part))
    record: dict[str, Any] = {
        "relative_path": relative,
        "directory": rel(path.parent, data_dir),
        "filename": path.name,
        "stem": path.stem,
        "suffix": path.suffix.lower(),
        "role_hint": infer_image_role(path),
        "stem_tokens": "|".join(stem_tokens),
        "parent_tokens": "|".join(parent_tokens),
        "all_path_tokens": "|".join(parent_tokens + stem_tokens),
    }
    for idx, token in enumerate(stem_tokens[:12], start=1):
        record[f"stem_token_{idx}"] = token
    for idx, token in enumerate(parent_tokens[:12], start=1):
        record[f"parent_token_{idx}"] = token
    if include_stats:
        record.update(extract_image_stats(path))
    return record


def build_image_manifest(paths: list[Path], data_dir: Path, max_stats: int) -> pd.DataFrame:
    records = []
    for index, path in enumerate(paths):
        records.append(image_manifest_record(path, data_dir, include_stats=index < max_stats))
    return pd.DataFrame(records)


def table_value_sets(table_paths: list[Path]) -> list[dict[str, Any]]:
    value_sets = []
    for path in table_paths:
        try:
            df = read_table(path)
        except Exception:
            continue
        df.columns = [str(c).strip() for c in df.columns]
        for col in df.columns:
            series = df[col].dropna()
            if series.empty:
                continue
            unique_count = int(series.nunique(dropna=True))
            if unique_count > 20000:
                continue
            values = {str(v).lower() for v in series.unique()}
            token_values = set()
            for value in list(values)[:25000]:
                token_values.update(tokenize_text(value))
            value_sets.append(
                {
                    "table": path,
                    "column": col,
                    "unique_count": unique_count,
                    "values": values,
                    "token_values": token_values,
                }
            )
    return value_sets


def image_join_hints(image_manifest: pd.DataFrame, table_paths: list[Path], data_dir: Path) -> list[dict[str, Any]]:
    if image_manifest.empty:
        return []
    hints = []
    image_stems = {str(v).lower() for v in image_manifest["stem"].dropna().unique()}
    image_filenames = {str(v).lower() for v in image_manifest["filename"].dropna().unique()}
    image_tokens = set()
    for value in image_manifest.get("all_path_tokens", pd.Series(dtype=str)).dropna():
        image_tokens.update(str(value).split("|"))
    image_tokens = {token for token in image_tokens if token}

    for item in table_value_sets(table_paths):
        exact_stem_overlap = len(image_stems.intersection(item["values"]))
        exact_filename_overlap = len(image_filenames.intersection(item["values"]))
        token_overlap = len(image_tokens.intersection(item["values"].union(item["token_values"])))
        score = exact_stem_overlap * 10 + exact_filename_overlap * 10 + token_overlap
        if score <= 0:
            continue
        hints.append(
            {
                "table": rel(item["table"], data_dir),
                "column": item["column"],
                "unique_values": item["unique_count"],
                "exact_stem_overlap": exact_stem_overlap,
                "exact_filename_overlap": exact_filename_overlap,
                "token_overlap": token_overlap,
                "score": score,
            }
        )
    return sorted(hints, key=lambda row: row["score"], reverse=True)[:50]


def profile_data(data_dir: Path) -> dict[str, Any]:
    all_files = sorted(p for p in data_dir.rglob("*") if p.is_file())
    table_paths = [p for p in all_files if p.suffix.lower() in TABULAR_EXTENSIONS]
    image_paths = [p for p in all_files if p.suffix.lower() in IMAGE_EXTENSIONS]
    other_paths = [p for p in all_files if p not in table_paths and p not in image_paths]
    image_manifest = build_image_manifest(image_paths, data_dir, max_stats=5000)
    return {
        "data_dir": str(data_dir.resolve()),
        "description": read_description(data_dir),
        "file_counts": {
            "total_files": len(all_files),
            "tabular_files": len(table_paths),
            "image_files": len(image_paths),
            "other_files": len(other_paths),
        },
        "tables": [summarize_table(path, data_dir) for path in table_paths],
        "images": summarize_images(image_paths, data_dir),
        "image_join_hints": image_join_hints(image_manifest, table_paths, data_dir),
        "other_files": [rel(path, data_dir) for path in other_paths[:200]],
    }


def write_markdown(profile: dict[str, Any], path: Path) -> None:
    lines = [
        "# Data Profile",
        "",
        f"Data directory: `{profile['data_dir']}`",
        "",
        "## File Counts",
        "",
    ]
    for key, value in profile["file_counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Description Files", ""])
    for desc in profile["description"]["files"]:
        lines.append(f"- `{desc.get('path')}`")
    if not profile["description"]["files"]:
        lines.append("- None found")
    lines.extend(["", "## Tables", ""])
    for table in profile["tables"]:
        lines.append(f"### `{table['path']}`")
        if "error" in table:
            lines.append(f"- Error: {table['error']}")
            lines.append("")
            continue
        lines.append(f"- Shape: {table['rows']} rows x {len(table['columns'])} columns")
        lines.append(f"- Roles: {', '.join(table['roles'])}")
        lines.append(f"- Columns: {', '.join(table['columns'])}")
        if table["id_like_columns"]:
            lines.append(f"- ID-like columns: {', '.join(table['id_like_columns'])}")
        lines.append("")
    lines.extend(["## Images", ""])
    lines.append(f"- Count: {profile['images']['count']}")
    for directory, count in sorted(profile["images"]["directories"].items()):
        lines.append(f"- `{directory}`: {count}")
    if profile.get("image_join_hints"):
        lines.extend(["", "## Image Join Hints", ""])
        for hint in profile["image_join_hints"][:12]:
            lines.append(
                "- "
                f"`{hint['table']}` column `{hint['column']}` "
                f"(score {hint['score']}, token overlap {hint['token_overlap']}, "
                f"stem overlap {hint['exact_stem_overlap']})"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recursively profile held-out data before writing a custom analysis.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out", default="analysis_outputs/data_profile.json")
    parser.add_argument("--markdown", default="analysis_outputs/data_profile.md")
    parser.add_argument("--image-manifest", default="analysis_outputs/image_manifest.csv")
    parser.add_argument("--max-image-stats", type=int, default=5000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data directory does not exist: {data_dir}")
    profile = profile_data(data_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2, default=safe_json), encoding="utf-8")
    if args.markdown:
        write_markdown(profile, Path(args.markdown))
    if args.image_manifest:
        image_paths = sorted(p for p in data_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        manifest = build_image_manifest(image_paths, data_dir, max_stats=args.max_image_stats)
        manifest_path = Path(args.image_manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(manifest_path, index=False)
    print(f"Profiled {profile['file_counts']['tabular_files']} tables and {profile['file_counts']['image_files']} images.")
    print(f"Wrote {out_path}")
    if args.image_manifest:
        print(f"Wrote {args.image_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
