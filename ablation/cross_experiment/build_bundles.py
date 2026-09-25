#!/usr/bin/env python3
"""Build species-level annotation and embedding bundles for cross-session LCA."""

import argparse
import copy
import csv
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG = SCRIPT_DIR / "datasets_ia35.yaml"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source(experiment, annotation_data, embedding_data, selection_mode="one"):
    annotations = annotation_data.get("annotations", [])
    images = annotation_data.get("images", [])
    if not annotations:
        raise ValueError(f"{experiment} contains no frame-sampling annotations.")

    annotation_uuids = [annotation.get("uuid") for annotation in annotations]
    if None in annotation_uuids or len(annotation_uuids) != len(set(annotation_uuids)):
        raise ValueError(f"{experiment} has missing or duplicate annotation UUIDs.")

    image_uuids = [image.get("uuid") for image in images]
    if None in image_uuids or len(image_uuids) != len(set(image_uuids)):
        raise ValueError(f"{experiment} has missing or duplicate image UUIDs.")
    missing_images = {
        annotation.get("image_uuid") for annotation in annotations
    } - set(image_uuids)
    if missing_images:
        raise ValueError(
            f"{experiment} annotations reference {len(missing_images)} missing images."
        )

    if selection_mode not in {"one", "many"}:
        raise ValueError(f"Unsupported selection_mode={selection_mode!r}.")
    groups = [
        (annotation.get("viewpoint"), annotation.get("tracking_id"))
        for annotation in annotations
    ]
    if selection_mode == "one" and len(groups) != len(set(groups)):
        raise ValueError(
            f"{experiment} is not one-best: duplicate viewpoint/tracking-ID groups exist."
        )

    embeddings, embedding_uuids = embedding_data
    embeddings = np.asarray(embeddings)
    embedding_uuids = list(embedding_uuids)
    if len(embeddings) != len(annotations):
        raise ValueError(
            f"{experiment} has {len(annotations)} annotations but "
            f"{len(embeddings)} embeddings."
        )
    if embedding_uuids != annotation_uuids:
        raise ValueError(
            f"{experiment} embedding UUID order does not match its annotation JSON."
        )
    return embeddings


def combine_experiments(
    group_name,
    expected_species,
    sources,
    selection_mode="one",
    global_tid_registry=None,
):
    category_id_by_species = {
        species: category_id for category_id, species in enumerate(expected_species)
    }
    combined_annotations = []
    combined_images = []
    combined_embeddings = []
    combined_embedding_uuids = []
    seen_annotation_uuids = set()
    image_by_uuid = {}
    mapping_rows = []
    source_rows = []
    excluded_rows = []
    next_global_tid = 1
    embedding_shape = None

    for source in sources:
        experiment = source["name"]
        fs_json = Path(source["fs_json"])
        embedding_pickle = Path(source["embedding_pickle"])
        annotation_data = load_json(fs_json)
        with embedding_pickle.open("rb") as file:
            embedding_data = pickle.load(file)
        embeddings = validate_source(
            experiment,
            annotation_data,
            embedding_data,
            selection_mode=selection_mode,
        )

        if embedding_shape is None:
            embedding_shape = embeddings.shape[1:]
        elif embeddings.shape[1:] != embedding_shape:
            raise ValueError(
                f"{experiment} embedding shape {embeddings.shape[1:]} differs from "
                f"the expected {embedding_shape}."
            )

        source_category_map = {
            category["id"]: category.get("species")
            for category in annotation_data.get("categories", [])
        }
        annotations = annotation_data["annotations"]
        valid_indices = []
        valid_tids = set()
        for index, annotation in enumerate(annotations):
            tracking_id = annotation.get("tracking_id")
            if isinstance(tracking_id, bool) or not isinstance(tracking_id, int):
                raise ValueError(
                    f"{experiment} annotation {annotation['uuid']} has non-integer "
                    f"tracking_id={tracking_id!r}."
                )
            if tracking_id < 0:
                excluded_rows.append(
                    {
                        "species_group": group_name,
                        "source_experiment": experiment,
                        "original_tracking_id": tracking_id,
                        "viewpoint": annotation.get("viewpoint"),
                        "annotation_uuid": annotation["uuid"],
                        "image_uuid": annotation.get("image_uuid"),
                        "reason": "negative tracker sentinel",
                    }
                )
                continue
            valid_indices.append(index)
            valid_tids.add(tracking_id)

        global_tid_by_original = {}
        for original_tid in sorted(valid_tids):
            registry_key = (experiment, original_tid)
            if global_tid_registry is not None:
                if registry_key not in global_tid_registry:
                    raise ValueError(
                        f"{experiment} TID {original_tid} is absent from the configured "
                        "global tracking-ID registry."
                    )
                global_tid_by_original[original_tid] = global_tid_registry[registry_key]
            else:
                global_tid_by_original[original_tid] = next_global_tid
                next_global_tid += 1

        valid_annotations = [annotations[index] for index in valid_indices]
        for original_tid in sorted(valid_tids):
            tid_annotations = [
                annotation
                for annotation in valid_annotations
                if annotation["tracking_id"] == original_tid
            ]
            mapping_rows.append(
                {
                    "species_group": group_name,
                    "global_tracking_id": global_tid_by_original[original_tid],
                    "source_experiment": experiment,
                    "original_tracking_id": original_tid,
                    "source_tracking_key": f"{experiment}:{original_tid}",
                    "viewpoints": ",".join(
                        sorted({annotation["viewpoint"] for annotation in tid_annotations})
                    ),
                    "annotation_count": len(tid_annotations),
                }
            )

        referenced_image_uuids = set()
        for index in valid_indices:
            source_annotation = annotations[index]
            annotation_uuid = source_annotation["uuid"]
            if annotation_uuid in seen_annotation_uuids:
                raise ValueError(
                    f"Duplicate annotation UUID across experiments: {annotation_uuid}"
                )
            seen_annotation_uuids.add(annotation_uuid)

            species = source_category_map.get(source_annotation.get("category_id"))
            if species not in category_id_by_species:
                raise ValueError(
                    f"{experiment} annotation {annotation_uuid} has unexpected "
                    f"species {species!r}."
                )

            original_tid = source_annotation["tracking_id"]
            annotation = copy.deepcopy(source_annotation)
            annotation["tracking_id"] = global_tid_by_original[original_tid]
            annotation["original_tracking_id"] = original_tid
            annotation["source_experiment"] = experiment
            annotation["source_tracking_key"] = f"{experiment}:{original_tid}"
            annotation["category_id"] = category_id_by_species[species]
            combined_annotations.append(annotation)
            combined_embeddings.append(embeddings[index])
            combined_embedding_uuids.append(annotation_uuid)
            referenced_image_uuids.add(annotation["image_uuid"])

        for image in annotation_data.get("images", []):
            image_uuid = image["uuid"]
            if image_uuid not in referenced_image_uuids:
                continue
            existing = image_by_uuid.get(image_uuid)
            if existing is not None:
                if existing != image:
                    raise ValueError(
                        f"Image UUID collision with different records: {image_uuid}"
                    )
                continue
            copied_image = copy.deepcopy(image)
            image_by_uuid[image_uuid] = copied_image
            combined_images.append(copied_image)

        source_rows.append(
            {
                "species_group": group_name,
                "source_experiment": experiment,
                "source_fs_json": str(fs_json),
                "source_embedding_pickle": str(embedding_pickle),
                "source_annotations": len(annotations),
                "included_annotations": len(valid_indices),
                "excluded_negative_tid_annotations": len(annotations) - len(valid_indices),
                "included_tracking_ids": len(valid_tids),
                "fs_json_sha256": sha256(fs_json),
                "embedding_pickle_sha256": sha256(embedding_pickle),
            }
        )

    if not combined_annotations:
        raise ValueError(f"No valid annotations were found for {group_name}.")
    if len(combined_annotation_uuids := [
        annotation["uuid"] for annotation in combined_annotations
    ]) != len(set(combined_annotation_uuids)):
        raise AssertionError("Combined annotation UUIDs are not unique.")
    if combined_embedding_uuids != combined_annotation_uuids:
        raise AssertionError("Combined embedding UUID order is invalid.")
    global_tracking_ids = [row["global_tracking_id"] for row in mapping_rows]
    if len(global_tracking_ids) != len(set(global_tracking_ids)):
        raise AssertionError("Global tracking IDs are not unique.")
    if global_tid_registry is None and sorted(global_tracking_ids) != list(
        range(1, len(mapping_rows) + 1)
    ):
        raise AssertionError("Global tracking IDs are not contiguous and deterministic.")

    bundle = {
        "categories": [
            {"id": category_id, "species": species}
            for species, category_id in category_id_by_species.items()
        ],
        "images": combined_images,
        "annotations": combined_annotations,
    }
    embedding_bundle = (
        np.asarray(combined_embeddings),
        combined_embedding_uuids,
    )
    return bundle, embedding_bundle, mapping_rows, source_rows, excluded_rows


def write_tsv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=rows[0].keys(),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def load_tracking_id_registry(path):
    registry = {}
    global_ids = set()
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            key = (row["source_experiment"], int(row["original_tracking_id"]))
            global_tid = int(row["global_tracking_id"])
            if key in registry:
                raise ValueError(f"Duplicate tracking-ID registry key: {key}")
            if global_tid in global_ids:
                raise ValueError(
                    f"Duplicate global tracking ID {global_tid} in registry {path}."
                )
            registry[key] = global_tid
            global_ids.add(global_tid)
    if not registry:
        raise ValueError(f"Tracking-ID registry is empty: {path}")
    return registry


def resolve_path(path):
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def write_lca_post_config(
    output_dir,
    annotation_filename,
    embedding_filename,
    allowed_image_root,
):
    config_path = output_dir / "lca_post_config.yaml"
    config = {
        "data_dir_out": str(output_dir),
        "data_dir_in": str(output_dir),
        "data_video": True,
        "post_allowed_dir": str(allowed_image_root),
        "log_dirname": "logs",
        "image_dirname": "",
        "model_dirname": str(REPO_ROOT / "VAREID" / "models"),
        "image_out_file": "unused_image_data.json",
        "video_out_file": "unused_video_data.json",
        "import_logfile": "unused_import.txt",
        "dt_dirname": "unused_detector",
        "dt_model": "unused",
        "dt_logfile": "unused_detector.txt",
        "dt_gt_file": None,
        "dt_filtered_out_file": None,
        "dt_video_out_file": "unused_vid_annots.json",
        "dt_image_out_file": "unused_img_annots.json",
        "si_dirname": "unused_species_identifier",
        "si_out_file": "unused_si_annots.json",
        "si_logfile": "unused_species_identifier.txt",
        "vc_dirname": "unused_viewpoint_classifier",
        "vc_model": "unused",
        "vc_out_file": "unused_vc_annots.json",
        "vc_logfile": "unused_viewpoint_classifier.txt",
        "ia_dirname": "unused_ia_classifier",
        "ia_model": "unused",
        "ia_out_file": "unused_ia_annots.json",
        "ia_filtered_out_file": "unused_ia_annots_filtered.json",
        "ia_logfile": "unused_ia_classifier.txt",
        "fs_dirname": "",
        "fs_out_file": annotation_filename,
        "fs_logfile": "unused_frame_sampling.txt",
        "fs_stage1_out_file": None,
        "mid_dirname": "",
        "mid_model": "conservationxlabs/miewid-msv3",
        "mid_out_file": embedding_filename,
        "mid_logfile": "unused_miewid.txt",
        "lca_dirname": "lca_stability_universal",
        "lca_verifiers_probs": "verifiers_probs.json",
        "lca_subunit_logfile": "lca_algorithm.txt",
        "lca_logfile": "lca.txt",
        "lca_separate_viewpoints": True,
        "lca_out_prefix": "lca",
        "lca_out_suffix": "annots",
        "post_dirname": "post",
        "post_db_file": "post_ui_decision_db.db",
        "post_left_out_file": "post_left_annots.json",
        "post_right_out_file": "post_right_annots.json",
        "post_logfile": "post.txt",
        "gui_logfile": "gui.txt",
        "interaction_mode": "database",
    }
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False)
    return config_path


def write_group(output_root, group, sources, settings):
    group_name = group["name"]
    output_dir = output_root / group_name
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle, embeddings, mappings, source_rows, excluded = combine_experiments(
        group_name,
        group["expected_species"],
        sources,
        selection_mode=settings["selection_mode"],
        global_tid_registry=settings.get("global_tid_registry"),
    )

    annotation_path = output_dir / settings["annotation_filename"]
    embedding_path = output_dir / settings["embedding_filename"]
    mapping_tsv_path = output_dir / "tracking_id_map.tsv"
    mapping_json_path = output_dir / "tracking_id_map.json"
    source_manifest_path = output_dir / "source_manifest.tsv"
    metadata_path = output_dir / "metadata.yaml"

    with annotation_path.open("w", encoding="utf-8") as file:
        json.dump(bundle, file, indent=2)
        file.write("\n")
    with embedding_path.open("wb") as file:
        pickle.dump(embeddings, file)
    write_tsv(mapping_tsv_path, mappings)
    write_tsv(source_manifest_path, source_rows)
    with mapping_json_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "species_group": group_name,
                "global_tracking_ids": mappings,
                "excluded_annotations": excluded,
            },
            file,
            indent=2,
        )
        file.write("\n")

    left_count = sum(
        annotation.get("viewpoint") == "left" for annotation in bundle["annotations"]
    )
    right_count = sum(
        annotation.get("viewpoint") == "right" for annotation in bundle["annotations"]
    )
    metadata = {
        "species_group": group_name,
        "display_name": group["display_name"],
        "ia_threshold": settings["ia_threshold"],
        "selection_mode": settings["selection_mode"],
        "selection_policy": settings.get("selection_policy"),
        "source_experiments": [source["name"] for source in sources],
        "annotation_file": str(annotation_path),
        "embedding_file": str(embedding_path),
        "tracking_id_map_tsv": str(mapping_tsv_path),
        "tracking_id_map_json": str(mapping_json_path),
        "tracking_id_registry": settings.get("global_tid_registry_path"),
        "source_manifest": str(source_manifest_path),
        "annotations": len(bundle["annotations"]),
        "left_annotations": left_count,
        "right_annotations": right_count,
        "global_tracking_ids": len(mappings),
        "excluded_negative_tid_annotations": len(excluded),
        "embedding_shape": list(embeddings[0].shape),
        "lca": {
            "status": "not_run",
            "separate_viewpoints": True,
            "planned_output_dir": str(output_dir / "lca_stability_universal"),
        },
    }
    with metadata_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(metadata, file, sort_keys=False)

    projection_summary = None
    if group.get("ground_truth_projection"):
        from ablation.cross_experiment.project_ground_truth import (
            write_ground_truth_projection,
        )

        projection = group["ground_truth_projection"]
        projection_summary = write_ground_truth_projection(
            output_dir=output_dir,
            species_group=group_name,
            ia_threshold=settings["ia_threshold"],
            mapping_rows=mappings,
            within_session_ground_truth_path=resolve_path(
                projection["within_session_ground_truth"]
            ),
            cross_session_ground_truth_path=resolve_path(
                projection["cross_session_ground_truth"]
            ),
            source_identity_map_path=resolve_path(projection["source_identity_map"]),
        )

    lca_post_config = write_lca_post_config(
        output_dir,
        annotation_path.name,
        embedding_path.name,
        settings["allowed_image_root"],
    )

    return {
        "species_group": group_name,
        "experiments": len(sources),
        "annotations": len(bundle["annotations"]),
        "left_annotations": left_count,
        "right_annotations": right_count,
        "global_tracking_ids": len(mappings),
        "excluded_negative_tid_annotations": len(excluded),
        "annotation_file": str(annotation_path),
        "embedding_file": str(embedding_path),
        "tracking_id_map": str(mapping_tsv_path),
        "metadata": str(metadata_path),
        "ground_truth_projection": (
            projection_summary["projection_yaml"] if projection_summary else ""
        ),
        "lca_post_config": str(lca_post_config),
        "lca_status": "not_run",
    }


def main():
    args = parse_args()
    with args.config.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    results_root = Path(config["results_root"])
    output_root = args.output_root or Path(config["output_root"])
    selection_mode = config.get("selection_mode", "one")
    ia_threshold = float(config.get("ia_threshold", 0.35))
    threshold_label = config.get("threshold_label", "35")
    source_dir_template = config.get("source_dir_template")
    annotation_filename = config.get(
        "annotation_filename", f"combined_{selection_mode}_fs_annots.json"
    )
    embedding_filename = config.get(
        "embedding_filename", f"combined_{selection_mode}_miewid_embeddings.pickle"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in config["groups"]:
        sources = []
        registry_path = group.get("tracking_id_registry")
        registry_path = resolve_path(registry_path) if registry_path else None
        registry = load_tracking_id_registry(registry_path) if registry_path else None
        for experiment in group["experiments"]:
            experiment_root = results_root / f"{experiment}_test_mavric_imageomics"
            if source_dir_template:
                source_root = experiment_root / source_dir_template.format(
                    experiment=experiment,
                    threshold_label=threshold_label,
                )
                fs_json = source_root / config["source_fs_json"]
                embedding_pickle = source_root / config["source_embedding_pickle"]
            else:
                fs_json = experiment_root / "frame_sampling_IA35" / "fs_annots.json"
                embedding_pickle = (
                    experiment_root / "miew_id_IA_35" / "miewid_embeddings.pickle"
                )
            if not fs_json.is_file() or not embedding_pickle.is_file():
                raise FileNotFoundError(
                    f"Missing {selection_mode} source for {experiment}: "
                    f"{fs_json}, {embedding_pickle}"
                )
            sources.append(
                {
                    "name": experiment,
                    "fs_json": fs_json,
                    "embedding_pickle": embedding_pickle,
                }
            )
        rows.append(
            write_group(
                output_root,
                group,
                sources,
                {
                    "ia_threshold": ia_threshold,
                    "selection_mode": selection_mode,
                    "selection_policy": config.get("selection_policy"),
                    "annotation_filename": annotation_filename,
                    "embedding_filename": embedding_filename,
                    "global_tid_registry": registry,
                    "global_tid_registry_path": (
                        str(registry_path) if registry_path else None
                    ),
                    "allowed_image_root": results_root,
                },
            )
        )

    manifest_path = output_root / "bundle_manifest.tsv"
    write_tsv(manifest_path, rows)
    print(f"Built {len(rows)} cross-experiment species bundles.")
    for row in rows:
        print(
            f"  {row['species_group']}: {row['annotations']} annotations, "
            f"{row['global_tracking_ids']} global TIDs, "
            f"{row['excluded_negative_tid_annotations']} excluded"
        )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
