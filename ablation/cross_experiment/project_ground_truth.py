#!/usr/bin/env python3
"""Project curated cross-session identities into a pipeline track-ID namespace."""

import csv
from pathlib import Path

import yaml


VIEWPOINTS = ("left", "right")


def load_yaml(path):
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def write_tsv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def load_source_identity_map(path):
    identities = {}
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            bundle_tid = int(row["global_tracking_id"])
            if bundle_tid in identities:
                raise ValueError(f"Duplicate source identity bundle TID {bundle_tid}.")
            identities[bundle_tid] = {
                "source_experiment": row["source_experiment"],
                "source_ground_truth_id": int(row["source_ground_truth_id"]),
            }
    if not identities:
        raise ValueError(f"Source identity map is empty: {path}")
    return identities


def index_within_session_ground_truth(data):
    indexed = {}
    for experiment, experiment_data in data["experiments"].items():
        for identity in experiment_data["individuals"]:
            key = (experiment, int(identity["id"]))
            if key in indexed:
                raise ValueError(f"Duplicate within-session identity {key}.")
            indexed[key] = {
                viewpoint: [int(tid) for tid in identity.get(viewpoint, [])]
                for viewpoint in VIEWPOINTS
            }
    return indexed


def project_ground_truth(
    species_group,
    ia_threshold,
    mapping_rows,
    within_session_ground_truth,
    cross_session_ground_truth,
    source_identity_map,
):
    pipeline_tracks = {}
    for row in mapping_rows:
        key = (row["source_experiment"], int(row["original_tracking_id"]))
        if key in pipeline_tracks:
            raise ValueError(f"Duplicate pipeline track mapping {key}.")
        pipeline_tracks[key] = {
            "global_tracking_id": int(row["global_tracking_id"]),
            "viewpoints": set(filter(None, row["viewpoints"].split(","))),
        }

    within_identities = index_within_session_ground_truth(within_session_ground_truth)
    projected_individuals = []
    labeled_rows = []
    missing_rows = []
    assignment_by_track_view = {}

    for cross_identity in cross_session_ground_truth["individuals"]:
        cross_identity_id = int(cross_identity["id"])
        projected = {
            "id": cross_identity_id,
            "left": [],
            "right": [],
            "source_identity_bundle_ids": {
                viewpoint: [int(value) for value in cross_identity.get(viewpoint, [])]
                for viewpoint in VIEWPOINTS
            },
        }

        for viewpoint in VIEWPOINTS:
            projected_tids = set()
            for source_bundle_tid in projected["source_identity_bundle_ids"][viewpoint]:
                if source_bundle_tid not in source_identity_map:
                    raise ValueError(
                        f"Cross-session GT references unknown source identity bundle "
                        f"TID {source_bundle_tid}."
                    )
                source_identity = source_identity_map[source_bundle_tid]
                identity_key = (
                    source_identity["source_experiment"],
                    source_identity["source_ground_truth_id"],
                )
                if identity_key not in within_identities:
                    raise ValueError(
                        f"Source identity {identity_key} is absent from within-session GT."
                    )

                for original_tid in within_identities[identity_key][viewpoint]:
                    track_key = (identity_key[0], original_tid)
                    pipeline_track = pipeline_tracks.get(track_key)
                    if pipeline_track is None or viewpoint not in pipeline_track["viewpoints"]:
                        missing_rows.append(
                            {
                                "species_group": species_group,
                                "cross_session_identity_id": cross_identity_id,
                                "viewpoint": viewpoint,
                                "source_identity_bundle_tid": source_bundle_tid,
                                "source_experiment": identity_key[0],
                                "source_ground_truth_id": identity_key[1],
                                "original_tracking_id": original_tid,
                                "reason": "not represented after IA/RA selection",
                            }
                        )
                        continue

                    global_tid = pipeline_track["global_tracking_id"]
                    assignment_key = (viewpoint, global_tid)
                    previous = assignment_by_track_view.get(assignment_key)
                    if previous is not None and previous != cross_identity_id:
                        raise ValueError(
                            f"Pipeline TID {global_tid}/{viewpoint} maps to cross-session "
                            f"identities {previous} and {cross_identity_id}."
                        )
                    assignment_by_track_view[assignment_key] = cross_identity_id
                    if global_tid in projected_tids:
                        continue
                    projected_tids.add(global_tid)
                    labeled_rows.append(
                        {
                            "species_group": species_group,
                            "cross_session_identity_id": cross_identity_id,
                            "viewpoint": viewpoint,
                            "global_tracking_id": global_tid,
                            "source_identity_bundle_tid": source_bundle_tid,
                            "source_experiment": identity_key[0],
                            "source_ground_truth_id": identity_key[1],
                            "original_tracking_id": original_tid,
                        }
                    )
            projected[viewpoint] = sorted(projected_tids)
        projected_individuals.append(projected)

    unlabeled_rows = []
    for row in mapping_rows:
        global_tid = int(row["global_tracking_id"])
        for viewpoint in filter(None, row["viewpoints"].split(",")):
            if (viewpoint, global_tid) in assignment_by_track_view:
                continue
            unlabeled_rows.append(
                {
                    "species_group": species_group,
                    "viewpoint": viewpoint,
                    "global_tracking_id": global_tid,
                    "source_experiment": row["source_experiment"],
                    "original_tracking_id": int(row["original_tracking_id"]),
                }
            )

    represented_identity_ids = {
        identity["id"]
        for identity in projected_individuals
        if identity["left"] or identity["right"]
    }
    projection = {
        "metadata": {
            "species_group": species_group,
            "ia_threshold": ia_threshold,
            "tracking_id_namespace": "pipeline_global_tracking_id",
            "identity_id_namespace": "existing_cross_session_ground_truth_id",
            "purpose": "evaluation_only_not_lca_input",
            "counts": {
                "cross_session_identities": len(projected_individuals),
                "represented_cross_session_identities": len(represented_identity_ids),
                "labeled_track_viewpoint_assignments": len(labeled_rows),
                "unlabeled_track_viewpoint_assignments": len(unlabeled_rows),
                "ground_truth_track_viewpoints_missing_at_threshold": len(missing_rows),
            },
        },
        "individuals": projected_individuals,
    }
    return projection, labeled_rows, unlabeled_rows, missing_rows


def write_ground_truth_projection(
    output_dir,
    species_group,
    ia_threshold,
    mapping_rows,
    within_session_ground_truth_path,
    cross_session_ground_truth_path,
    source_identity_map_path,
):
    output_dir = Path(output_dir)
    source_identity_map = load_source_identity_map(source_identity_map_path)
    projection, labeled, unlabeled, missing = project_ground_truth(
        species_group=species_group,
        ia_threshold=ia_threshold,
        mapping_rows=mapping_rows,
        within_session_ground_truth=load_yaml(within_session_ground_truth_path),
        cross_session_ground_truth=load_yaml(cross_session_ground_truth_path),
        source_identity_map=source_identity_map,
    )
    projection["metadata"].update(
        {
            "within_session_ground_truth": str(within_session_ground_truth_path),
            "cross_session_ground_truth": str(cross_session_ground_truth_path),
            "source_identity_map": str(source_identity_map_path),
        }
    )

    projection_path = output_dir / "ground_truth_projection.yaml"
    labeled_path = output_dir / "ground_truth_track_map.tsv"
    unlabeled_path = output_dir / "unlabeled_tracking_ids.tsv"
    threshold_label = int(round(float(ia_threshold) * 100))
    missing_path = output_dir / f"ground_truth_missing_at_ia{threshold_label:02d}.tsv"
    with projection_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(projection, file, sort_keys=False)

    write_tsv(
        labeled_path,
        labeled,
        [
            "species_group",
            "cross_session_identity_id",
            "viewpoint",
            "global_tracking_id",
            "source_identity_bundle_tid",
            "source_experiment",
            "source_ground_truth_id",
            "original_tracking_id",
        ],
    )
    write_tsv(
        unlabeled_path,
        unlabeled,
        [
            "species_group",
            "viewpoint",
            "global_tracking_id",
            "source_experiment",
            "original_tracking_id",
        ],
    )
    write_tsv(
        missing_path,
        missing,
        [
            "species_group",
            "cross_session_identity_id",
            "viewpoint",
            "source_identity_bundle_tid",
            "source_experiment",
            "source_ground_truth_id",
            "original_tracking_id",
            "reason",
        ],
    )
    return {
        "projection_yaml": str(projection_path),
        "ground_truth_track_map": str(labeled_path),
        "unlabeled_tracking_ids": str(unlabeled_path),
        "missing_ground_truth_assignments": str(missing_path),
        **projection["metadata"]["counts"],
    }
