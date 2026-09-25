#!/usr/bin/env python3
"""Remove negative tracker sentinels from selected per-session RA inputs.

The tracker uses negative IDs for detections that do not belong to a valid
track.  Historical frame-sampling outputs grouped those detections as if they
formed a track.  This utility removes such selected annotations and their
aligned MiewID embeddings, updates the generated manifests and metadata, and
backs up every modified artifact before writing.

Pooled cross-session bundles are deliberately outside the manifests consumed
by this utility and are never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = Path(
    "/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth"
)
OPERATING_MANIFEST = (
    REPO_ROOT / "ablation/ra_selection/generated/operating_point_manifest.tsv"
)
SWEEP_MANIFEST = REPO_ROOT / "ablation/ia_threshold/generated/pre_lca_manifest.tsv"
DEFAULT_BACKUP_ROOT = RESULTS_ROOT / "negative_tracking_id_cleanup_backup_20260825"
DEFAULT_AUDIT = (
    REPO_ROOT
    / "ablation/ia_threshold/generated/negative_tracking_id_cleanup.tsv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the cleanup. Without this flag, only report affected inputs.",
    )
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--audit-tsv", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def is_negative_tracking_sentinel(annotation: dict[str, object]) -> bool:
    tracking_id = annotation.get("tracking_id")
    return (
        isinstance(tracking_id, (int, float))
        and not isinstance(tracking_id, bool)
        and tracking_id < 0
    )


def atomic_json_dump(path: Path, value: object) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def atomic_pickle_dump(path: Path, value: object) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as handle:
        pickle.dump(value, handle)
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def atomic_yaml_dump(path: Path, value: object) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        yaml.safe_dump(value, handle, sort_keys=False)
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def backup_path(source: Path, backup_root: Path) -> Path:
    try:
        relative = source.relative_to(RESULTS_ROOT)
    except ValueError:
        relative = Path("repository") / source.name
    return backup_root / relative


def backup_file(source: Path, backup_root: Path) -> Path:
    destination = backup_path(source, backup_root)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def selected_group_count(annotations: list[dict[str, object]]) -> int:
    return len(
        {
            (annotation.get("viewpoint"), annotation.get("tracking_id"))
            for annotation in annotations
        }
    )


def collect_tasks(
    operating_rows: list[dict[str, str]], sweep_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    for row in operating_rows:
        tasks.append(
            {
                "manifest_kind": "operating_035",
                "manifest_row": row,
                "dataset": row["dataset"],
                "threshold": "0.35",
                "json_path": Path(row["fs_json"]),
                "pickle_path": Path(row["embedding_pickle"]),
                "metadata_path": Path(row["metadata_yaml"]),
            }
        )
    for row in sweep_rows:
        tasks.append(
            {
                "manifest_kind": "threshold_sweep",
                "manifest_row": row,
                "dataset": row["dataset"],
                "threshold": f"{float(row['threshold']):.2f}",
                "json_path": Path(row["fs_json"]),
                "pickle_path": Path(row["embedding_pickle"]),
                "metadata_path": Path(row["metadata_yaml"]),
            }
        )
    return tasks


def main() -> None:
    args = parse_args()
    operating_rows = read_tsv(OPERATING_MANIFEST)
    sweep_rows = read_tsv(SWEEP_MANIFEST)
    tasks = collect_tasks(operating_rows, sweep_rows)
    affected: list[tuple[dict[str, object], dict[str, object], list[int]]] = []

    for task in tasks:
        json_path = task["json_path"]
        with json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        annotations = data.get("annotations", [])
        remove_indices = [
            index
            for index, annotation in enumerate(annotations)
            if is_negative_tracking_sentinel(annotation)
        ]
        for index in remove_indices:
            affected.append((task, annotations[index], remove_indices))

    if not affected:
        print("No negative tracking sentinels remain in selected per-session inputs.")
        return

    unique_tasks = {
        (str(task["json_path"]), str(task["pickle_path"])): (task, indices)
        for task, _, indices in affected
    }
    print(
        f"Found {len(affected)} selected sentinel annotation(s) in "
        f"{len(unique_tasks)} per-session input pair(s)."
    )
    for task, annotation, _ in affected:
        print(
            f"{task['dataset']} theta={task['threshold']}: "
            f"tracking_id={annotation.get('tracking_id')} "
            f"uuid={annotation.get('uuid')}"
        )

    if not args.apply:
        print("Dry run only; rerun with --apply to modify the inputs.")
        return

    backup_file(OPERATING_MANIFEST, args.backup_root)
    backup_file(SWEEP_MANIFEST, args.backup_root)
    audit_rows: list[dict[str, object]] = []

    for task, remove_indices in unique_tasks.values():
        json_path = task["json_path"]
        pickle_path = task["pickle_path"]
        metadata_path = task["metadata_path"]
        for required in (json_path, pickle_path, metadata_path):
            if not required.is_file():
                raise FileNotFoundError(required)

        with json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        annotations = data.get("annotations", [])
        with pickle_path.open("rb") as handle:
            embeddings, embedding_uuids = pickle.load(handle)
        annotation_uuids = [annotation["uuid"] for annotation in annotations]
        if annotation_uuids != list(embedding_uuids):
            raise ValueError(f"JSON/pickle UUID order differs: {json_path}")
        if len(embeddings) != len(annotations):
            raise ValueError(f"JSON/pickle length differs: {json_path}")

        remove_set = set(remove_indices)
        keep_indices = [index for index in range(len(annotations)) if index not in remove_set]
        removed_annotations = [annotations[index] for index in remove_indices]
        kept_annotations = [annotations[index] for index in keep_indices]
        kept_embeddings = (
            embeddings[keep_indices]
            if isinstance(embeddings, np.ndarray)
            else [embeddings[index] for index in keep_indices]
        )
        kept_uuids = [embedding_uuids[index] for index in keep_indices]

        json_backup = backup_file(json_path, args.backup_root)
        pickle_backup = backup_file(pickle_path, args.backup_root)
        metadata_backup = backup_file(metadata_path, args.backup_root)

        data["annotations"] = kept_annotations
        atomic_json_dump(json_path, data)
        atomic_pickle_dump(pickle_path, (kept_embeddings, kept_uuids))

        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = yaml.safe_load(handle)
        metadata["frame_sampling"]["num_annotations"] = len(kept_annotations)
        if "num_viewpoint_track_groups" in metadata["frame_sampling"]:
            metadata["frame_sampling"]["num_viewpoint_track_groups"] = (
                selected_group_count(kept_annotations)
            )
        metadata["miewid"]["num_embeddings"] = len(kept_embeddings)
        atomic_yaml_dump(metadata_path, metadata)

        row = task["manifest_row"]
        if task["manifest_kind"] == "operating_035":
            row["num_annotations"] = str(len(kept_annotations))
        else:
            row["selected_annotations"] = str(len(kept_annotations))

        for annotation in removed_annotations:
            audit_rows.append(
                {
                    "dataset": task["dataset"],
                    "threshold": task["threshold"],
                    "tracking_id": annotation.get("tracking_id"),
                    "viewpoint": annotation.get("viewpoint"),
                    "uuid": annotation.get("uuid"),
                    "ia_score": annotation.get("CA_score"),
                    "annotations_before": len(annotations),
                    "annotations_after": len(kept_annotations),
                    "selected_json": json_path,
                    "embedding_pickle": pickle_path,
                    "metadata_yaml": metadata_path,
                    "json_backup": json_backup,
                    "pickle_backup": pickle_backup,
                    "metadata_backup": metadata_backup,
                    "experiment_root": json_path.parent.parent,
                }
            )

    write_tsv(
        OPERATING_MANIFEST,
        operating_rows,
        list(operating_rows[0].keys()),
    )
    write_tsv(SWEEP_MANIFEST, sweep_rows, list(sweep_rows[0].keys()))
    write_tsv(args.audit_tsv, audit_rows, list(audit_rows[0].keys()))
    print(f"Removed {len(audit_rows)} selected sentinel annotation(s).")
    print(f"Backups: {args.backup_root}")
    print(f"Audit: {args.audit_tsv}")


if __name__ == "__main__":
    main()
