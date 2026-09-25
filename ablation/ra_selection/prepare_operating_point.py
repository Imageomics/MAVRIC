#!/usr/bin/env python3
"""Prepare reproducible pre-LCA artifacts for the selected RA operating point."""

import argparse
import csv
import json
import pickle
import shutil
from pathlib import Path

import yaml

from ablation.ra_selection.materialize_selected_embeddings import materialize


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SELECTION_MANIFEST = SCRIPT_DIR / "generated" / "manifest.tsv"
DEFAULT_EMBEDDING_MANIFEST = SCRIPT_DIR / "generated" / "embedding_manifest.tsv"
DEFAULT_OUTPUT_MANIFEST = SCRIPT_DIR / "generated" / "operating_point_manifest.tsv"
DEFAULT_RUN_NAME = "many_t05_q90_n10"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=DEFAULT_SELECTION_MANIFEST,
    )
    parser.add_argument(
        "--embedding-manifest",
        type=Path,
        default=DEFAULT_EMBEDDING_MANIFEST,
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=DEFAULT_OUTPUT_MANIFEST,
    )
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    return parser.parse_args()


def load_tsv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def validate_operating_point(config, path):
    expected = {
        ("thresholds", "t_seconds"): 5,
        ("thresholds", "frame_interval"): 15,
        ("thresholds", "quality_threshold_pct"): 0.9,
        ("settings", "selection_mode"): "many",
        ("settings", "num_RA_annots"): 10,
        ("settings", "use_ca_score"): True,
        ("settings", "use_viewpoint"): True,
    }
    for (section, key), value in expected.items():
        actual = config.get(section, {}).get(key)
        if actual != value:
            raise ValueError(
                f"Unexpected {section}.{key}={actual!r} in {path}; expected {value!r}."
            )


def lca_status(left_output, right_output):
    present = (left_output.is_file(), right_output.is_file())
    if all(present):
        return "complete"
    if any(present):
        return "partial"
    return "not_run"


def main():
    args = parse_args()
    selection_rows = load_tsv(args.selection_manifest)
    embedding_rows = load_tsv(args.embedding_manifest)

    selected_tasks = {
        row["dataset"]: row
        for row in selection_rows
        if row["run_name"] == args.run_name
    }
    embedding_tasks = {row["dataset"]: row for row in embedding_rows}
    if set(selected_tasks) != set(embedding_tasks):
        raise ValueError(
            "Selection/embedding dataset mismatch; "
            f"selection_only={sorted(set(selected_tasks) - set(embedding_tasks))}, "
            f"embedding_only={sorted(set(embedding_tasks) - set(selected_tasks))}"
        )
    if len(embedding_rows) != 13:
        raise ValueError(f"Expected 13 canonical datasets, found {len(embedding_rows)}.")

    output_rows = []
    for embedding_task in embedding_rows:
        dataset = embedding_task["dataset"]
        selection_task = selected_tasks[dataset]
        selected_json = Path(selection_task["output_json"])
        source_config = Path(selection_task["sampling_config"])
        union_pickle = Path(embedding_task["embedding_pickle"])
        if not selected_json.is_file():
            raise FileNotFoundError(f"Missing selected annotations: {selected_json}")
        if not source_config.is_file():
            raise FileNotFoundError(f"Missing sampling config: {source_config}")
        if not union_pickle.is_file():
            raise FileNotFoundError(f"Missing union embeddings: {union_pickle}")

        with source_config.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        validate_operating_point(config, source_config)

        run_dir = selected_json.parent
        config_snapshot = run_dir / "frame_sampling_config.yaml"
        selected_pickle = run_dir / "miewid_embeddings.pickle"
        metadata_path = run_dir / "operating_point_metadata.yaml"
        lca_dir = run_dir / "lca_stability_universal"
        left_output = lca_dir / "lca_left_annots.json"
        right_output = lca_dir / "lca_right_annots.json"

        shutil.copyfile(source_config, config_snapshot)
        annotation_count = materialize(
            selected_json,
            union_pickle,
            selected_pickle,
        )

        with selected_json.open("r", encoding="utf-8") as file:
            selected_data = json.load(file)
        with selected_pickle.open("rb") as file:
            selected_embeddings, selected_uuids = pickle.load(file)
        annotation_uuids = [
            annotation["uuid"] for annotation in selected_data["annotations"]
        ]
        if len(selected_embeddings) != annotation_count or selected_uuids != annotation_uuids:
            raise ValueError(f"Pre-LCA embedding validation failed for {dataset}.")

        status = lca_status(left_output, right_output)
        metadata = {
            "dataset": dataset,
            "species": dataset.split("_Experiment_", 1)[0],
            "run_name": args.run_name,
            "pre_lca_status": "ready",
            "source_ia_json": selection_task["input_json"],
            "frame_sampling": {
                "config": str(config_snapshot),
                "output": str(selected_json),
                "log": selection_task["run_log"],
                "num_annotations": annotation_count,
            },
            "miewid": {
                "model": embedding_task["model_url"],
                "union_cache": str(union_pickle),
                "selected_embeddings": str(selected_pickle),
                "num_embeddings": len(selected_embeddings),
            },
            "lca": {
                "status": status,
                "input_annotations": str(selected_json),
                "input_embeddings": str(selected_pickle),
                "planned_output_dir": str(lca_dir),
                "expected_left_output": str(left_output),
                "expected_right_output": str(right_output),
            },
        }
        with metadata_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(metadata, file, sort_keys=False)

        output_rows.append(
            {
                "task_id": embedding_task["task_id"],
                "dataset": dataset,
                "species": metadata["species"],
                "run_name": args.run_name,
                "source_ia_json": selection_task["input_json"],
                "sampling_config": str(config_snapshot),
                "fs_json": str(selected_json),
                "num_annotations": annotation_count,
                "embedding_pickle": str(selected_pickle),
                "metadata_yaml": str(metadata_path),
                "lca_dir": str(lca_dir),
                "left_output": str(left_output),
                "right_output": str(right_output),
                "pre_lca_status": "ready",
                "lca_status": status,
            }
        )

    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.output_manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=output_rows[0].keys(),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Prepared {len(output_rows)} operating-point datasets before LCA.")
    print(f"Manifest: {args.output_manifest}")
    for row in output_rows:
        print(
            f"  {row['dataset']}: {row['num_annotations']} annotations, "
            f"LCA={row['lca_status']}"
        )


if __name__ == "__main__":
    main()
