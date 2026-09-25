#!/usr/bin/env python3
"""Evaluate all completed RA configurations from cached union embeddings."""

import argparse
import csv
import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "generated" / "manifest.tsv"
DEFAULT_EMBEDDING_MANIFEST = SCRIPT_DIR / "generated" / "embedding_manifest.tsv"
DEFAULT_GROUND_TRUTHS = (
    SCRIPT_DIR / "grevys_ground_truth.yaml",
    SCRIPT_DIR / "plains_ground_truth.yaml",
    SCRIPT_DIR / "giraffe_ground_truth.yaml",
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--embedding-manifest",
        type=Path,
        default=DEFAULT_EMBEDDING_MANIFEST,
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        dest="ground_truths",
        help="Ground-truth YAML; repeat for multiple files (defaults to all species).",
    )
    parser.add_argument("--k", type=int, default=5)
    return parser.parse_args()


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def load_ground_truth(paths):
    mappings = {}
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file)
        for experiment, block in raw["experiments"].items():
            if experiment in mappings:
                raise ValueError(f"Duplicate GT experiment across files: {experiment}")
            mapping = {}
            for individual in block["individuals"]:
                identity = int(individual["id"])
                for viewpoint in ("left", "right"):
                    for tracking_id in individual.get(viewpoint, []):
                        key = (viewpoint, int(tracking_id))
                        if key in mapping:
                            raise ValueError(
                                f"Duplicate GT assignment for {experiment} {key}"
                            )
                        mapping[key] = identity
            mappings[experiment] = mapping
    return mappings


def average_precision_at_k(hits, total_relevant, k, paper_compatible=False):
    hits = np.asarray(hits[:k], dtype=bool)
    hit_positions = np.flatnonzero(hits)
    if hit_positions.size == 0:
        return 0.0
    precisions = [hits[: position + 1].mean() for position in hit_positions]
    if paper_compatible:
        denominator = hit_positions.size
    else:
        denominator = min(int(total_relevant), int(k))
    return float(np.sum(precisions) / denominator)


def retrieval_metrics(embeddings, metadata, k=5, exclude_same_tid=False):
    if len(metadata) != len(embeddings):
        raise ValueError("Embedding and metadata lengths do not match.")
    if not metadata:
        return {"map": 0.0, "hit": 0.0, "queries": 0}

    embeddings = np.asarray(embeddings, dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / np.maximum(norms, 1e-12)
    similarities = embeddings @ embeddings.T

    ap_values = []
    hit_values = []
    for query_index, query in enumerate(metadata):
        gallery = []
        for gallery_index, candidate in enumerate(metadata):
            if gallery_index == query_index:
                continue
            if candidate["viewpoint"] != query["viewpoint"]:
                continue
            if exclude_same_tid and candidate["tracking_id"] == query["tracking_id"]:
                continue
            gallery.append(gallery_index)

        relevant = [
            index
            for index in gallery
            if metadata[index]["identity"] == query["identity"]
        ]
        if exclude_same_tid and not relevant:
            continue

        ranked = sorted(
            gallery,
            key=lambda index: (-float(similarities[query_index, index]), index),
        )[:k]
        hits = [metadata[index]["identity"] == query["identity"] for index in ranked]
        ap_values.append(
            average_precision_at_k(
                hits,
                total_relevant=len(relevant),
                k=k,
                paper_compatible=not exclude_same_tid,
            )
        )
        hit_values.append(float(any(hits)))

    return {
        "map": float(np.mean(ap_values)) if ap_values else 0.0,
        "hit": float(np.mean(hit_values)) if hit_values else 0.0,
        "queries": len(ap_values),
    }


def fixed_query_metrics(
    query_embeddings,
    query_metadata,
    gallery_embeddings,
    gallery_metadata,
    gt_map,
    k=5,
):
    """Evaluate fixed one-best queries against a configuration-specific gallery."""
    if len(query_metadata) != len(query_embeddings):
        raise ValueError("Query embedding and metadata lengths do not match.")
    if len(gallery_metadata) != len(gallery_embeddings):
        raise ValueError("Gallery embedding and metadata lengths do not match.")
    if not query_metadata:
        return {"map": 0.0, "hit": 0.0, "queries": 0}

    query_embeddings = np.asarray(query_embeddings, dtype=np.float32)
    gallery_embeddings = np.asarray(gallery_embeddings, dtype=np.float32)
    query_embeddings /= np.maximum(
        np.linalg.norm(query_embeddings, axis=1, keepdims=True),
        1e-12,
    )
    if len(gallery_embeddings):
        gallery_embeddings /= np.maximum(
            np.linalg.norm(gallery_embeddings, axis=1, keepdims=True),
            1e-12,
        )
        similarities = query_embeddings @ gallery_embeddings.T
    else:
        similarities = np.empty((len(query_embeddings), 0), dtype=np.float32)

    identity_tracks = defaultdict(set)
    for (viewpoint, tracking_id), identity in gt_map.items():
        identity_tracks[(viewpoint, identity)].add(tracking_id)

    ap_values = []
    hit_values = []
    for query_index, query in enumerate(query_metadata):
        eligible_tids = identity_tracks[(query["viewpoint"], query["identity"])] - {
            query["tracking_id"]
        }
        if not eligible_tids:
            continue

        candidates = [
            index
            for index, candidate in enumerate(gallery_metadata)
            if candidate["viewpoint"] == query["viewpoint"]
            and candidate["tracking_id"] != query["tracking_id"]
        ]
        relevant = [
            index
            for index in candidates
            if gallery_metadata[index]["identity"] == query["identity"]
        ]
        ranked = sorted(
            candidates,
            key=lambda index: (-float(similarities[query_index, index]), index),
        )[:k]
        hits = [
            gallery_metadata[index]["identity"] == query["identity"]
            for index in ranked
        ]
        ap_values.append(
            average_precision_at_k(
                hits,
                total_relevant=len(relevant),
                k=k,
            )
        )
        hit_values.append(float(any(hits)))

    return {
        "map": float(np.mean(ap_values)) if ap_values else 0.0,
        "hit": float(np.mean(hit_values)) if hit_values else 0.0,
        "queries": len(ap_values),
    }


def load_embedding_cache(path):
    with Path(path).open("rb") as file:
        obj = pickle.load(file)
    if not isinstance(obj, (tuple, list)) or len(obj) != 2:
        raise TypeError(f"Unexpected embedding pickle format: {path}")
    embeddings, uuids = obj
    embeddings = np.asarray(embeddings)
    uuids = list(uuids)
    if embeddings.shape[0] != len(uuids):
        raise ValueError(f"Embedding/UUID length mismatch in {path}")
    return {uuid: embeddings[index] for index, uuid in enumerate(uuids)}


def summarize(rows, metric):
    values = np.asarray([float(row[metric]) for row in rows], dtype=float)
    return float(values.mean()), float(values.std(ddof=0))


def aggregate_results(rows, group_fields):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in group_fields)].append(row)

    aggregates = []
    for group_key in sorted(grouped):
        run_rows = grouped[group_key]
        first = run_rows[0]
        aggregate = {
            **dict(zip(group_fields, group_key)),
            "selection_mode": first["selection_mode"],
            "t_seconds": first["t_seconds"],
            "quality_threshold_pct": first["quality_threshold_pct"],
            "num_RA_annots": first["num_RA_annots"],
            "datasets": len(run_rows),
        }
        for metric in (
            "num_annotations",
            "num_gt_annotations",
            "num_non_id_annotations",
            "paper_map5",
            "paper_hit5",
            "strict_map5",
            "strict_hit5",
            "fixed_map5",
            "fixed_hit5",
        ):
            mean, std = summarize(run_rows, metric)
            aggregate[f"mean_{metric}"] = mean
            aggregate[f"std_{metric}"] = std
        aggregates.append(aggregate)
    return aggregates


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows available for {path}")
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    ground_truth = load_ground_truth(args.ground_truths or DEFAULT_GROUND_TRUTHS)

    with args.manifest.open("r", encoding="utf-8", newline="") as file:
        selection_tasks = list(csv.DictReader(file, delimiter="\t"))
    selection_datasets = {task["dataset"] for task in selection_tasks}
    if selection_datasets != set(ground_truth):
        raise ValueError(
            "Selection/GT dataset mismatch; "
            f"selection_only={sorted(selection_datasets - set(ground_truth))}, "
            f"gt_only={sorted(set(ground_truth) - selection_datasets)}"
        )

    with args.embedding_manifest.open("r", encoding="utf-8", newline="") as file:
        embedding_tasks = {
            task["dataset"]: task for task in csv.DictReader(file, delimiter="\t")
        }
    if set(embedding_tasks) != selection_datasets:
        raise ValueError(
            "Selection/embedding dataset mismatch; "
            f"selection_only={sorted(selection_datasets - set(embedding_tasks))}, "
            f"embedding_only={sorted(set(embedding_tasks) - selection_datasets)}"
        )

    caches = {}
    union_metadata = {}
    for dataset, task in embedding_tasks.items():
        embedding_path = Path(task["embedding_pickle"])
        if not embedding_path.is_file():
            raise FileNotFoundError(f"Missing union embedding: {embedding_path}")
        caches[dataset] = load_embedding_cache(embedding_path)
        union = load_json(task["union_json"])
        union_metadata[dataset] = {
            annotation["uuid"]: annotation
            for annotation in union.get("annotations", [])
        }

    task_by_dataset_run = {
        (task["dataset"], task["run_name"]): task for task in selection_tasks
    }
    fixed_queries = {}
    for dataset in sorted(selection_datasets):
        task = task_by_dataset_run[(dataset, "one_best")]
        selected = load_json(task["output_json"]).get("annotations", [])
        query_embeddings = []
        query_metadata = []
        for annotation in selected:
            uuid = annotation["uuid"]
            source_annotation = union_metadata[dataset][uuid]
            viewpoint = str(source_annotation.get("viewpoint", "unknown")).lower()
            tracking_id = int(source_annotation["tracking_id"])
            identity = ground_truth[dataset].get((viewpoint, tracking_id))
            if identity is None:
                continue
            query_embeddings.append(caches[dataset][uuid])
            query_metadata.append(
                {
                    "identity": identity,
                    "viewpoint": viewpoint,
                    "tracking_id": tracking_id,
                }
            )
        fixed_queries[dataset] = (query_embeddings, query_metadata)

    rows = []
    for task in selection_tasks:
        dataset = task["dataset"]
        selected = load_json(task["output_json"]).get("annotations", [])
        selected_uuids = [annotation["uuid"] for annotation in selected]
        cache = caches[dataset]
        metadata_by_uuid = union_metadata[dataset]
        gt_map = ground_truth[dataset]

        scored_embeddings = []
        scored_metadata = []
        for uuid in selected_uuids:
            if uuid not in cache or uuid not in metadata_by_uuid:
                raise KeyError(f"{dataset}/{task['run_name']} missing cached UUID {uuid}")
            annotation = metadata_by_uuid[uuid]
            viewpoint = str(annotation.get("viewpoint", "unknown")).lower()
            tracking_id = int(annotation["tracking_id"])
            identity = gt_map.get((viewpoint, tracking_id))
            if identity is None:
                continue
            scored_embeddings.append(cache[uuid])
            scored_metadata.append(
                {
                    "identity": identity,
                    "viewpoint": viewpoint,
                    "tracking_id": tracking_id,
                }
            )

        paper = retrieval_metrics(
            scored_embeddings,
            scored_metadata,
            k=args.k,
            exclude_same_tid=False,
        )
        strict = retrieval_metrics(
            scored_embeddings,
            scored_metadata,
            k=args.k,
            exclude_same_tid=True,
        )
        query_embeddings, query_metadata = fixed_queries[dataset]
        fixed = fixed_query_metrics(
            query_embeddings,
            query_metadata,
            scored_embeddings,
            scored_metadata,
            gt_map,
            k=args.k,
        )

        with Path(task["sampling_config"]).open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        rows.append(
            {
                "dataset": dataset,
                "species": dataset.split("_Experiment_", 1)[0],
                "run_name": task["run_name"],
                "selection_mode": config["settings"]["selection_mode"],
                "t_seconds": config["thresholds"]["t_seconds"],
                "quality_threshold_pct": config["thresholds"]["quality_threshold_pct"],
                "num_RA_annots": config["settings"]["num_RA_annots"],
                "num_annotations": len(selected_uuids),
                "num_gt_annotations": len(scored_metadata),
                "num_non_id_annotations": len(selected_uuids) - len(scored_metadata),
                "paper_map5": paper["map"],
                "paper_hit5": paper["hit"],
                "paper_queries": paper["queries"],
                "strict_map5": strict["map"],
                "strict_hit5": strict["hit"],
                "strict_queries": strict["queries"],
                "fixed_map5": fixed["map"],
                "fixed_hit5": fixed["hit"],
                "fixed_queries": fixed["queries"],
            }
        )

    output_root = Path(next(iter(embedding_tasks.values()))["union_json"]).parents[2]
    evaluation_dir = output_root / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    per_experiment_path = evaluation_dir / "all_per_experiment.csv"
    write_csv(per_experiment_path, rows)

    aggregate_rows = aggregate_results(rows, ("run_name",))
    aggregate_path = evaluation_dir / "all_aggregate.csv"
    write_csv(aggregate_path, aggregate_rows)

    species_rows = aggregate_results(rows, ("species", "run_name"))
    species_path = evaluation_dir / "species_aggregate.csv"
    write_csv(species_path, species_rows)

    print(f"Evaluated {len(rows)} dataset/configuration outputs.")
    print(f"Per-experiment results: {per_experiment_path}")
    print(f"Aggregate results: {aggregate_path}")
    print(f"Species results: {species_path}")


if __name__ == "__main__":
    main()
