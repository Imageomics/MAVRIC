#!/usr/bin/env python3
"""Build cross-experiment bundles with one representative per GT identity/viewpoint."""

import argparse
import copy
import json
import pickle
from pathlib import Path

import numpy as np
import yaml

from ablation.cross_experiment.build_bundles import (
    DEFAULT_CONFIG,
    load_json,
    sha256,
    validate_source,
    write_tsv,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def resolve_repo_path(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def representative_sort_key(annotation, image_by_uuid):
    score = annotation.get("CA_score")
    if score is None:
        raise ValueError(f"Annotation {annotation.get('uuid')} has no CA_score.")
    image = image_by_uuid[annotation["image_uuid"]]
    frame_number = image.get("frame_number")
    if frame_number is None:
        raise ValueError(f"Image {image['uuid']} has no frame_number.")
    return (-float(score), int(frame_number), annotation["uuid"])


def select_gt_representatives(group_name, expected_species, sources, ground_truth):
    category_id_by_species = {
        species: category_id for category_id, species in enumerate(expected_species)
    }
    combined_annotations = []
    combined_images = []
    combined_embeddings = []
    combined_embedding_uuids = []
    identity_rows = []
    selection_rows = []
    source_rows = []
    image_by_uuid_combined = {}
    seen_annotation_uuids = set()
    next_global_tid = 1
    embedding_shape = None

    source_names = [source["name"] for source in sources]
    if set(source_names) != set(ground_truth):
        raise ValueError(
            f"Ground-truth/source experiment mismatch for {group_name}: "
            f"sources={source_names}, ground_truth={sorted(ground_truth)}"
        )

    for source in sources:
        experiment = source["name"]
        fs_json = Path(source["fs_json"])
        embedding_pickle = Path(source["embedding_pickle"])
        annotation_data = load_json(fs_json)
        with embedding_pickle.open("rb") as file:
            embedding_data = pickle.load(file)
        embeddings = validate_source(experiment, annotation_data, embedding_data)
        if embedding_shape is None:
            embedding_shape = embeddings.shape[1:]
        elif embeddings.shape[1:] != embedding_shape:
            raise ValueError(f"Embedding shape mismatch in {experiment}.")

        annotations = annotation_data["annotations"]
        image_by_uuid = {
            image["uuid"]: image for image in annotation_data.get("images", [])
        }
        annotation_index = {
            (annotation["viewpoint"], int(annotation["tracking_id"])): index
            for index, annotation in enumerate(annotations)
        }
        source_category_map = {
            category["id"]: category.get("species")
            for category in annotation_data.get("categories", [])
        }

        assigned_keys = {}
        identities = ground_truth[experiment]["individuals"]
        identity_ids = [int(identity["id"]) for identity in identities]
        if len(identity_ids) != len(set(identity_ids)):
            raise ValueError(f"{experiment} contains duplicate ground-truth identity IDs.")

        selected_in_experiment = 0
        for identity in identities:
            source_identity_id = int(identity["id"])
            source_identity_key = f"{experiment}:ID_{source_identity_id}"
            global_tid = next_global_tid
            next_global_tid += 1
            selected_by_viewpoint = {}
            candidates_by_viewpoint = {}

            for viewpoint in ("left", "right"):
                candidate_tids = [int(tid) for tid in identity.get(viewpoint, [])]
                if len(candidate_tids) != len(set(candidate_tids)):
                    raise ValueError(
                        f"{source_identity_key}/{viewpoint} contains duplicate TIDs."
                    )
                candidates_by_viewpoint[viewpoint] = candidate_tids
                candidates = []
                for original_tid in candidate_tids:
                    key = (viewpoint, original_tid)
                    previous_identity = assigned_keys.get(key)
                    if previous_identity is not None:
                        raise ValueError(
                            f"{experiment} {key} is assigned to GT identities "
                            f"{previous_identity} and {source_identity_id}."
                        )
                    assigned_keys[key] = source_identity_id
                    if key not in annotation_index:
                        raise ValueError(
                            f"{source_identity_key} references missing {viewpoint} "
                            f"TID {original_tid}."
                        )
                    index = annotation_index[key]
                    candidates.append((index, annotations[index]))

                if not candidates:
                    continue
                selected_index, selected_source = min(
                    candidates,
                    key=lambda item: representative_sort_key(item[1], image_by_uuid),
                )
                selected_by_viewpoint[viewpoint] = selected_source
                selected_in_experiment += 1

                annotation_uuid = selected_source["uuid"]
                if annotation_uuid in seen_annotation_uuids:
                    raise ValueError(
                        f"Duplicate selected annotation UUID: {annotation_uuid}"
                    )
                seen_annotation_uuids.add(annotation_uuid)
                species = source_category_map.get(selected_source.get("category_id"))
                if species not in category_id_by_species:
                    raise ValueError(
                        f"{experiment} annotation {annotation_uuid} has unexpected "
                        f"species {species!r}."
                    )

                original_tid = int(selected_source["tracking_id"])
                selected = copy.deepcopy(selected_source)
                selected["tracking_id"] = global_tid
                selected["original_tracking_id"] = original_tid
                selected["source_experiment"] = experiment
                selected["source_tracking_key"] = f"{experiment}:{original_tid}"
                selected["source_ground_truth_id"] = source_identity_id
                selected["source_identity_key"] = source_identity_key
                selected["source_candidate_tracking_ids"] = candidate_tids
                selected["category_id"] = category_id_by_species[species]
                combined_annotations.append(selected)
                combined_embeddings.append(embeddings[selected_index])
                combined_embedding_uuids.append(annotation_uuid)

                image = image_by_uuid[selected["image_uuid"]]
                existing_image = image_by_uuid_combined.get(image["uuid"])
                if existing_image is not None and existing_image != image:
                    raise ValueError(
                        f"Image UUID collision with different records: {image['uuid']}"
                    )
                if existing_image is None:
                    copied_image = copy.deepcopy(image)
                    image_by_uuid_combined[image["uuid"]] = copied_image
                    combined_images.append(copied_image)

                selection_rows.append(
                    {
                        "species_group": group_name,
                        "global_tracking_id": global_tid,
                        "source_experiment": experiment,
                        "source_ground_truth_id": source_identity_id,
                        "source_identity_key": source_identity_key,
                        "viewpoint": viewpoint,
                        "selected_original_tracking_id": original_tid,
                        "candidate_tracking_ids": ",".join(map(str, candidate_tids)),
                        "candidate_count": len(candidate_tids),
                        "selected_annotation_uuid": annotation_uuid,
                        "selected_CA_score": selected_source["CA_score"],
                        "selected_frame_number": image["frame_number"],
                    }
                )

            if not selected_by_viewpoint:
                raise ValueError(f"{source_identity_key} has no represented viewpoint.")
            identity_rows.append(
                {
                    "species_group": group_name,
                    "global_tracking_id": global_tid,
                    "source_experiment": experiment,
                    "source_ground_truth_id": source_identity_id,
                    "source_identity_key": source_identity_key,
                    "has_left": "left" in selected_by_viewpoint,
                    "has_right": "right" in selected_by_viewpoint,
                    "selected_left_original_tid": (
                        selected_by_viewpoint.get("left", {}).get("tracking_id", "")
                    ),
                    "selected_right_original_tid": (
                        selected_by_viewpoint.get("right", {}).get("tracking_id", "")
                    ),
                    "left_candidate_tids": ",".join(
                        map(str, candidates_by_viewpoint["left"])
                    ),
                    "right_candidate_tids": ",".join(
                        map(str, candidates_by_viewpoint["right"])
                    ),
                }
            )

        left_assignments = {
            tid: identity_id
            for (viewpoint, tid), identity_id in assigned_keys.items()
            if viewpoint == "left"
        }
        right_assignments = {
            tid: identity_id
            for (viewpoint, tid), identity_id in assigned_keys.items()
            if viewpoint == "right"
        }
        cross_view_conflicts = [
            tid
            for tid in set(left_assignments) & set(right_assignments)
            if left_assignments[tid] != right_assignments[tid]
        ]
        if cross_view_conflicts:
            raise ValueError(
                f"{experiment} assigns shared TIDs to different cross-view identities: "
                f"{cross_view_conflicts}"
            )

        source_rows.append(
            {
                "species_group": group_name,
                "source_experiment": experiment,
                "source_fs_json": str(fs_json),
                "source_embedding_pickle": str(embedding_pickle),
                "source_annotations": len(annotations),
                "ground_truth_identities": len(identities),
                "ground_truth_tid_annotations": len(assigned_keys),
                "selected_representatives": selected_in_experiment,
                "non_id_annotations": len(annotations) - len(assigned_keys),
                "fs_json_sha256": sha256(fs_json),
                "embedding_pickle_sha256": sha256(embedding_pickle),
            }
        )

    annotation_uuids = [a["uuid"] for a in combined_annotations]
    if combined_embedding_uuids != annotation_uuids:
        raise AssertionError("Representative embedding UUID order is invalid.")
    groups = [(a["viewpoint"], a["tracking_id"]) for a in combined_annotations]
    if len(groups) != len(set(groups)):
        raise AssertionError("Representative bundle is not one-per-identity/viewpoint.")
    if sorted(row["global_tracking_id"] for row in identity_rows) != list(
        range(1, len(identity_rows) + 1)
    ):
        raise AssertionError("Global identity tracking IDs are not contiguous.")

    bundle = {
        "categories": [
            {"id": category_id, "species": species}
            for species, category_id in category_id_by_species.items()
        ],
        "images": combined_images,
        "annotations": combined_annotations,
    }
    return (
        bundle,
        (np.asarray(combined_embeddings), combined_embedding_uuids),
        identity_rows,
        selection_rows,
        source_rows,
    )


def write_group(output_root, group, sources, ground_truth):
    output_dir = output_root / group["name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle, embeddings, identities, selections, source_rows = select_gt_representatives(
        group["name"], group["expected_species"], sources, ground_truth
    )

    annotation_path = output_dir / "combined_gt_representatives_fs_annots.json"
    embedding_path = output_dir / "combined_gt_representatives_miewid_embeddings.pickle"
    identity_map_path = output_dir / "identity_map.tsv"
    identity_map_json_path = output_dir / "identity_map.json"
    selection_path = output_dir / "representative_selection.tsv"
    source_manifest_path = output_dir / "source_manifest.tsv"
    metadata_path = output_dir / "metadata.yaml"

    with annotation_path.open("w", encoding="utf-8") as file:
        json.dump(bundle, file, indent=2)
        file.write("\n")
    with embedding_path.open("wb") as file:
        pickle.dump(embeddings, file)
    write_tsv(identity_map_path, identities)
    write_tsv(selection_path, selections)
    write_tsv(source_manifest_path, source_rows)
    with identity_map_json_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "species_group": group["name"],
                "global_session_identities": identities,
                "representative_selections": selections,
            },
            file,
            indent=2,
        )
        file.write("\n")

    left_count = sum(a["viewpoint"] == "left" for a in bundle["annotations"])
    right_count = sum(a["viewpoint"] == "right" for a in bundle["annotations"])
    metadata = {
        "species_group": group["name"],
        "display_name": group["display_name"],
        "ia_threshold": 0.35,
        "source_selection_mode": "one_per_tracking_id_and_viewpoint",
        "combined_selection_mode": "highest_CA_per_GT_identity_and_viewpoint",
        "tracking_id_semantics": "unique source-session ground-truth identity",
        "source_experiments": [source["name"] for source in sources],
        "ground_truth_yaml": str(resolve_repo_path(group["ground_truth_yaml"])),
        "annotation_file": str(annotation_path),
        "embedding_file": str(embedding_path),
        "identity_map": str(identity_map_path),
        "representative_selection": str(selection_path),
        "source_manifest": str(source_manifest_path),
        "session_identities": len(identities),
        "annotations": len(bundle["annotations"]),
        "left_annotations": left_count,
        "right_annotations": right_count,
        "embedding_shape": list(embeddings[0].shape),
        "lca": {
            "status": "not_run",
            "separate_viewpoints": True,
            "planned_output_dir": str(output_dir / "lca_stability_universal"),
        },
    }
    with metadata_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(metadata, file, sort_keys=False)

    return {
        "species_group": group["name"],
        "experiments": len(sources),
        "session_identities": len(identities),
        "annotations": len(bundle["annotations"]),
        "left_annotations": left_count,
        "right_annotations": right_count,
        "annotation_file": str(annotation_path),
        "embedding_file": str(embedding_path),
        "identity_map": str(identity_map_path),
        "representative_selection": str(selection_path),
        "metadata": str(metadata_path),
        "lca_status": "not_run",
    }


def main():
    args = parse_args()
    with args.config.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    results_root = Path(config["results_root"])
    output_root = args.output_root or Path(config["gt_representative_output_root"])
    output_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for group in config["groups"]:
        gt_path = resolve_repo_path(group["ground_truth_yaml"])
        with gt_path.open("r", encoding="utf-8") as file:
            ground_truth = yaml.safe_load(file)["experiments"]
        sources = []
        for experiment in group["experiments"]:
            experiment_root = results_root / f"{experiment}_test_mavric_imageomics"
            sources.append(
                {
                    "name": experiment,
                    "fs_json": experiment_root
                    / "frame_sampling_IA35"
                    / "fs_annots.json",
                    "embedding_pickle": experiment_root
                    / "miew_id_IA_35"
                    / "miewid_embeddings.pickle",
                }
            )
        rows.append(write_group(output_root, group, sources, ground_truth))

    manifest_path = output_root / "bundle_manifest.tsv"
    write_tsv(manifest_path, rows)
    print(f"Built {len(rows)} GT-representative cross-experiment bundles.")
    for row in rows:
        print(
            f"  {row['species_group']}: {row['session_identities']} identities, "
            f"{row['annotations']} representatives "
            f"({row['left_annotations']} left, {row['right_annotations']} right)"
        )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
