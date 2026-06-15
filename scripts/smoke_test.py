from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def write_tiny_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEElEQVR4nGP4z8DwHwwMDAwA"
        "BgAB/2gHnQAAAABJRU5ErkJggg=="
    )
    path.write_bytes(base64.b64decode(payload))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="award_b_adaptive_smoke_") as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        train_dir = data_dir / "train"
        val_dir = data_dir / "val"
        train_dir.mkdir(parents=True)
        val_dir.mkdir(parents=True)

        rng = np.random.default_rng(11)
        jurisdictions = np.array(["CA", "NY", "TX"])
        categories = np.array(["all_drugs", "all_opioids"])
        train_periods = [f"p{i:03d}" for i in range(8)]
        val_periods = [f"v{i:03d}" for i in range(2)]

        train_cov = pd.DataFrame(
            [
                {
                    "period_id": period,
                    "jurisdiction": state,
                    "unemployment_rate": rng.uniform(2, 8),
                    "gtrends_overdose": rng.uniform(0, 100),
                    "state_doh_release": "naloxone overdose opioid response",
                }
                for period in train_periods
                for state in jurisdictions
            ]
        )
        val_cov = pd.DataFrame(
            [
                {
                    "period_id": period,
                    "jurisdiction": state,
                    "unemployment_rate": rng.uniform(2, 8),
                    "gtrends_overdose": rng.uniform(0, 100),
                    "state_doh_release": "",
                }
                for period in val_periods
                for state in jurisdictions
            ]
        )
        labels = []
        for _, row in train_cov.iterrows():
            for category in categories:
                base = 7.0 + 0.4 * row["unemployment_rate"] + 0.03 * row["gtrends_overdose"]
                labels.append(
                    {
                        "period_id": row["period_id"],
                        "jurisdiction": row["jurisdiction"],
                        "overdose_category": category,
                        "rate_per_10000_ed_visits": base + (2.0 if category == "all_opioids" else 0.0),
                    }
                )
        sample = []
        row_id = 1
        for _, row in val_cov.iterrows():
            for category in categories:
                sample.append(
                    {
                        "row_id": row_id,
                        "period_id": row["period_id"],
                        "jurisdiction": row["jurisdiction"],
                        "overdose_category": category,
                        "rate_per_10000_ed_visits": 0.0,
                    }
                )
                row_id += 1

        train_cov.to_csv(train_dir / "covariates.csv", index=False)
        val_cov.to_csv(val_dir / "covariates.csv", index=False)
        pd.DataFrame(labels).to_csv(train_dir / "dose_sys_train.csv", index=False)
        pd.DataFrame(sample).to_csv(data_dir / "sample_submission.csv", index=False)
        write_tiny_png(train_dir / "image_sidecars" / "density-map-state-CA-period-p000-tile-alpha.png")
        write_tiny_png(val_dir / "image_sidecars" / "heldout-density-state-NY-period-v000-tile-beta.png")
        (data_dir / "Data_Description.md").write_text(
            "Predict `rate_per_10000_ed_visits` for every row in `sample_submission.csv`.",
            encoding="utf-8",
        )

        analysis_dir = tmp_path / "analysis_outputs"
        run(
            [
                sys.executable,
                str(repo_root / "scripts" / "profile_data.py"),
                "--data-dir",
                str(data_dir),
                "--out",
                str(analysis_dir / "data_profile.json"),
                "--markdown",
                str(analysis_dir / "data_profile.md"),
                "--image-manifest",
                str(analysis_dir / "image_manifest.csv"),
            ],
            repo_root,
        )
        manifest = pd.read_csv(analysis_dir / "image_manifest.csv")
        assert len(manifest) == 2
        assert "all_path_tokens" in manifest.columns
        assert "luminance_mean" in manifest.columns or "stats_error" in manifest.columns

        submission = pd.DataFrame(sample)[["row_id", "rate_per_10000_ed_visits"]]
        submission["rate_per_10000_ed_visits"] = float(pd.DataFrame(labels)["rate_per_10000_ed_visits"].median())
        submission_path = tmp_path / "submission.csv"
        submission.to_csv(submission_path, index=False)
        run(
            [
                sys.executable,
                str(repo_root / "scripts" / "validate_submission.py"),
                "--data-dir",
                str(data_dir),
                "--submission",
                str(submission_path),
                "--json-out",
                str(analysis_dir / "validation.json"),
            ],
            repo_root,
        )

        report_md = analysis_dir / "report.md"
        report_md.write_text("# Smoke Test\n\nAdaptive helper utilities passed.", encoding="utf-8")
        report_pdf = tmp_path / "report.pdf"
        run(
            [
                sys.executable,
                str(repo_root / "scripts" / "report_utils.py"),
                "--markdown",
                str(report_md),
                "--out",
                str(report_pdf),
            ],
            repo_root,
        )
        assert report_pdf.exists() and report_pdf.stat().st_size > 500

    print("Adaptive helper smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
