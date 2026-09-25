#!/usr/bin/env python3
"""Generate immutable configs and a Slurm task manifest for the RA sweep."""

import argparse
import csv
import itertools
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASETS = SCRIPT_DIR / "datasets_15fps.yaml"
DEFAULT_GENERATED_DIR = SCRIPT_DIR / "generated"

T_SECONDS = (5, 10, 15)
QUALITY_THRESHOLDS = (0.7, 0.8, 0.9)
RA_CAPS = (3, 5, 10)


def run_specs():
    yield "one_best", {
        "thresholds": {
            "t_seconds": 15,
            "quality_threshold_pct": 0.8,
        },
        "settings": {
            "selection_mode": "one",
            "num_RA_annots": 1,
        },
    }

    for t_seconds, quality, cap in itertools.product(
        T_SECONDS, QUALITY_THRESHOLDS, RA_CAPS
    ):
        quality_label = f"{int(round(quality * 100)):02d}"
        name = f"many_t{t_seconds:02d}_q{quality_label}_n{cap:02d}"
        yield name, {
            "thresholds": {
                "t_seconds": t_seconds,
                "quality_threshold_pct": quality,
            },
            "settings": {
                "selection_mode": "many",
                "num_RA_annots": cap,
            },
        }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", type=Path, default=DEFAULT_DATASETS)
    parser.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    with args.datasets.open("r", encoding="utf-8") as file:
        suite = yaml.safe_load(file)

    datasets = suite["datasets"]
    frame_interval = int(suite["frame_interval"])
    output_root = Path(suite["output_root"])
    specs = list(run_specs())

    if frame_interval != 15:
        raise ValueError("This ablation is intentionally restricted to 15 fps inputs.")
    if len(datasets) != 13:
        raise ValueError(f"Expected 13 canonical datasets, found {len(datasets)}.")
    if len(specs) != 28:
        raise AssertionError(f"Expected 28 configurations, found {len(specs)}.")

    missing = [item["input_json"] for item in datasets if not Path(item["input_json"]).is_file()]
    if missing:
        raise FileNotFoundError("Missing IA input files:\n" + "\n".join(missing))

    config_root = args.generated_dir / "configs"
    config_root.mkdir(parents=True, exist_ok=True)
    rows = []

    for dataset in datasets:
        dataset_name = dataset["name"]
        input_json = Path(dataset["input_json"]).resolve()

        for run_name, partial_config in specs:
            config = {
                "thresholds": {
                    **partial_config["thresholds"],
                    "frame_interval": frame_interval,
                },
                "settings": {
                    **partial_config["settings"],
                    "use_ca_score": True,
                    "use_viewpoint": True,
                    "seed": 123456789,
                },
            }

            config_path = config_root / dataset_name / f"{run_name}.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as file:
                yaml.safe_dump(config, file, sort_keys=False)

            run_dir = output_root / dataset_name / run_name
            rows.append(
                {
                    "task_id": len(rows),
                    "dataset": dataset_name,
                    "run_name": run_name,
                    "input_json": str(input_json),
                    "sampling_config": str(config_path.resolve()),
                    "output_json": str(run_dir / "fs_annots.json"),
                    "run_log": str(run_dir / "frame_sampling.log"),
                }
            )

    args.generated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.generated_dir / "manifest.tsv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=rows[0].keys(),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(specs)} configs x {len(datasets)} datasets = {len(rows)} tasks")
    print(f"Manifest: {manifest_path.resolve()}")
    print(f"Output root: {output_root}")


if __name__ == "__main__":
    main()
