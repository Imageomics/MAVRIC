#!/usr/bin/env python3
"""Generate immutable configs and a task manifest for the IA threshold sweep."""

import argparse
import csv
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASETS = SCRIPT_DIR / "datasets_15fps.yaml"
DEFAULT_GENERATED_DIR = SCRIPT_DIR / "generated"
THRESHOLD_LABELS = tuple(range(40, 100, 5))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", type=Path, default=DEFAULT_DATASETS)
    parser.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    return parser.parse_args()


def frame_sampling_config(frame_interval):
    return {
        "thresholds": {
            "t_seconds": 5,
            "frame_interval": frame_interval,
            "quality_threshold_pct": 0.9,
        },
        "settings": {
            "selection_mode": "many",
            "num_RA_annots": 10,
            "use_ca_score": True,
            "use_viewpoint": True,
            "seed": 123456789,
        },
    }


def output_paths(dataset_name, input_json, threshold_label):
    experiment_root = input_json.parent.parent
    output_dir = experiment_root / f"{dataset_name}_IA_{threshold_label:02d}"
    return {
        "output_dir": output_dir,
        "filtered_json": output_dir
        / "ia_classifier"
        / f"ia_annots_filtered_{threshold_label:02d}.json",
        "config_snapshot": output_dir
        / "frame_sampling"
        / "frame_sampling_config.yaml",
        "fs_json": output_dir / "frame_sampling" / "fs_annots.json",
        "filter_log": output_dir / "logs" / "ia_filtering.log",
        "fs_log": output_dir / "logs" / "frame_sampling.log",
    }


def build_rows(datasets, sampling_config_path):
    rows = []
    for dataset in datasets:
        dataset_name = dataset["name"]
        input_json = Path(dataset["input_json"]).resolve()
        for threshold_label in THRESHOLD_LABELS:
            paths = output_paths(dataset_name, input_json, threshold_label)
            rows.append(
                {
                    "task_id": len(rows),
                    "dataset": dataset_name,
                    "threshold_label": f"{threshold_label:02d}",
                    "threshold": f"{threshold_label / 100:.2f}",
                    "source_json": str(input_json),
                    "output_dir": str(paths["output_dir"]),
                    "filtered_json": str(paths["filtered_json"]),
                    "sampling_config": str(sampling_config_path.resolve()),
                    "config_snapshot": str(paths["config_snapshot"]),
                    "fs_json": str(paths["fs_json"]),
                    "filter_log": str(paths["filter_log"]),
                    "fs_log": str(paths["fs_log"]),
                }
            )
    return rows


def main():
    args = parse_args()
    with args.datasets.open("r", encoding="utf-8") as file:
        suite = yaml.safe_load(file)

    datasets = suite["datasets"]
    frame_interval = int(suite["frame_interval"])
    if frame_interval != 15:
        raise ValueError("This sweep is intentionally restricted to canonical 15 fps inputs.")
    if len(datasets) != 13:
        raise ValueError(f"Expected 13 canonical datasets, found {len(datasets)}.")

    missing = [item["input_json"] for item in datasets if not Path(item["input_json"]).is_file()]
    if missing:
        raise FileNotFoundError("Missing IA35 input files:\n" + "\n".join(missing))

    args.generated_dir.mkdir(parents=True, exist_ok=True)
    config_path = args.generated_dir / "frame_sampling_config.yaml"
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(frame_sampling_config(frame_interval), file, sort_keys=False)

    rows = build_rows(datasets, config_path)
    expected = len(datasets) * len(THRESHOLD_LABELS)
    if len(rows) != expected:
        raise AssertionError(f"Expected {expected} tasks, generated {len(rows)}.")

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

    print(
        f"Generated {len(THRESHOLD_LABELS)} thresholds x "
        f"{len(datasets)} datasets = {len(rows)} tasks"
    )
    print(f"Manifest: {manifest_path.resolve()}")
    print(f"Frame-sampling config: {config_path.resolve()}")


if __name__ == "__main__":
    main()
