#!/usr/bin/env python3
"""Materialize threshold-specific embeddings and reproducibility metadata."""

import argparse
import csv
import json
import pickle
from pathlib import Path

import yaml

from ablation.ra_selection.materialize_selected_embeddings import materialize


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "generated" / "manifest.tsv"
DEFAULT_EMBEDDING_MANIFEST = SCRIPT_DIR / "generated" / "embedding_manifest.tsv"
DEFAULT_OUTPUT_MANIFEST = SCRIPT_DIR / "generated" / "pre_lca_manifest.tsv"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
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
    return parser.parse_args()


def load_tsv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def viewpoint_track_count(data):
    return len(
        {
            (annotation.get("viewpoint"), annotation.get("tracking_id"))
            for annotation in data.get("annotations", [])
        }
    )


def main():
    args = parse_args()
    tasks = load_tsv(args.manifest)
    embedding_tasks = {
        row["dataset"]: row for row in load_tsv(args.embedding_manifest)
    }
    if len(tasks) != 156:
        raise ValueError(f"Expected 156 threshold tasks, found {len(tasks)}.")
    if len(embedding_tasks) != 13:
        raise ValueError(f"Expected 13 embedding tasks, found {len(embedding_tasks)}.")

    output_rows = []
    for task in tasks:
        dataset = task["dataset"]
        embedding_task = embedding_tasks.get(dataset)
        if embedding_task is None:
            raise KeyError(f"No embedding union task exists for {dataset}.")

        filtered_json = Path(task["filtered_json"])
        fs_json = Path(task["fs_json"])
        config_snapshot = Path(task["config_snapshot"])
        union_pickle = Path(embedding_task["embedding_pickle"])
        for required in (filtered_json, fs_json, config_snapshot, union_pickle):
            if not required.is_file():
                raise FileNotFoundError(f"Missing pre-LCA input: {required}")

        output_dir = Path(task["output_dir"])
        selected_pickle = output_dir / "miew_id" / "miewid_embeddings.pickle"
        annotation_count = materialize(fs_json, union_pickle, selected_pickle)

        filtered = load_json(filtered_json)
        selected = load_json(fs_json)
        with selected_pickle.open("rb") as file:
            embeddings, embedding_uuids = pickle.load(file)
        selected_uuids = [
            annotation["uuid"] for annotation in selected.get("annotations", [])
        ]
        if len(embeddings) != annotation_count or list(embedding_uuids) != selected_uuids:
            raise ValueError(f"Embedding validation failed for {dataset}/IA_{task['threshold_label']}.")

        lca_dir = output_dir / "lca_stability_universal"
        left_output = lca_dir / "lca_left_annots.json"
        right_output = lca_dir / "lca_right_annots.json"
        if left_output.is_file() and right_output.is_file():
            lca_status = "complete"
        elif left_output.is_file() or right_output.is_file():
            lca_status = "partial"
        else:
            lca_status = "not_run"

        metadata_path = output_dir / "metadata.yaml"
        metadata = {
            "dataset": dataset,
            "ia_threshold": float(task["threshold"]),
            "ia_filter_rule": f"CA_score > {task['threshold']}",
            "source_ia35_json": task["source_json"],
            "pre_lca_status": "ready",
            "ia_filtering": {
                "output": str(filtered_json),
                "log": task["filter_log"],
                "num_annotations": len(filtered.get("annotations", [])),
                "num_viewpoint_track_groups": viewpoint_track_count(filtered),
            },
            "frame_sampling": {
                "config": str(config_snapshot),
                "output": str(fs_json),
                "log": task["fs_log"],
                "num_annotations": annotation_count,
                "num_viewpoint_track_groups": viewpoint_track_count(selected),
            },
            "miewid": {
                "model": embedding_task["model_url"],
                "union_cache": str(union_pickle),
                "selected_embeddings": str(selected_pickle),
                "num_embeddings": len(embeddings),
            },
            "lca": {
                "status": lca_status,
                "planned_output_dir": str(lca_dir),
                "expected_left_output": str(left_output),
                "expected_right_output": str(right_output),
            },
        }
        with metadata_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(metadata, file, sort_keys=False)

        output_rows.append(
            {
                "task_id": task["task_id"],
                "dataset": dataset,
                "threshold_label": task["threshold_label"],
                "threshold": task["threshold"],
                "filtered_json": str(filtered_json),
                "filtered_annotations": len(filtered.get("annotations", [])),
                "fs_json": str(fs_json),
                "selected_annotations": annotation_count,
                "embedding_pickle": str(selected_pickle),
                "metadata_yaml": str(metadata_path),
                "lca_dir": str(lca_dir),
                "pre_lca_status": "ready",
                "lca_status": lca_status,
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

    print(f"Prepared {len(output_rows)} threshold-specific datasets before LCA.")
    print(f"Manifest: {args.output_manifest.resolve()}")


if __name__ == "__main__":
    main()
