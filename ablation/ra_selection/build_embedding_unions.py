#!/usr/bin/env python3
"""Build one annotation union per experiment for cached MiewID inference."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "generated" / "manifest.tsv"
DEFAULT_DATASETS = SCRIPT_DIR / "datasets_15fps.yaml"
DEFAULT_EMBEDDING_MANIFEST = SCRIPT_DIR / "generated" / "embedding_manifest.tsv"
MODEL_URL = "conservationxlabs/miewid-msv3"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--datasets", type=Path, default=DEFAULT_DATASETS)
    parser.add_argument(
        "--embedding-manifest",
        type=Path,
        default=DEFAULT_EMBEDDING_MANIFEST,
    )
    return parser.parse_args()


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    args = parse_args()
    with args.datasets.open("r", encoding="utf-8") as file:
        suite = yaml.safe_load(file)
    output_root = Path(suite["output_root"])

    with args.manifest.open("r", encoding="utf-8", newline="") as file:
        tasks = list(csv.DictReader(file, delimiter="\t"))

    by_dataset = defaultdict(list)
    for task in tasks:
        by_dataset[task["dataset"]].append(task)

    dataset_names = [dataset["name"] for dataset in suite["datasets"]]
    if set(by_dataset) != set(dataset_names):
        missing = sorted(set(dataset_names) - set(by_dataset))
        unexpected = sorted(set(by_dataset) - set(dataset_names))
        raise ValueError(
            f"Dataset manifest mismatch; missing={missing}, unexpected={unexpected}."
        )

    embedding_rows = []
    for dataset in dataset_names:
        dataset_tasks = by_dataset[dataset]
        if len(dataset_tasks) != 28:
            raise ValueError(f"{dataset} has {len(dataset_tasks)} tasks, expected 28.")

        source_paths = {Path(task["input_json"]) for task in dataset_tasks}
        if len(source_paths) != 1:
            raise ValueError(f"{dataset} has multiple source IA files: {source_paths}")
        source_path = source_paths.pop()

        selected_uuids = set()
        for task in dataset_tasks:
            output_path = Path(task["output_json"])
            if not output_path.is_file():
                raise FileNotFoundError(f"Missing completed selection: {output_path}")
            output = load_json(output_path)
            selected_uuids.update(
                annotation["uuid"] for annotation in output.get("annotations", [])
            )

        source = load_json(source_path)
        source_annotations = {
            annotation["uuid"]: annotation
            for annotation in source.get("annotations", [])
        }
        missing_uuids = selected_uuids - source_annotations.keys()
        if missing_uuids:
            raise ValueError(
                f"{dataset} has {len(missing_uuids)} selected UUIDs missing from IA input."
            )

        annotations = [
            annotation
            for annotation in source.get("annotations", [])
            if annotation["uuid"] in selected_uuids
        ]
        image_uuids = {annotation["image_uuid"] for annotation in annotations}
        images = [
            image
            for image in source.get("images", [])
            if image["uuid"] in image_uuids
        ]
        if len(images) != len(image_uuids):
            raise ValueError(
                f"{dataset} is missing {len(image_uuids) - len(images)} referenced images."
            )

        union_dir = output_root / dataset / "embedding_union"
        union_dir.mkdir(parents=True, exist_ok=True)
        union_json = union_dir / "union_fs_annots.json"
        with union_json.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "categories": source.get("categories", []),
                    "images": images,
                    "annotations": annotations,
                },
                file,
                indent=2,
            )

        embedding_rows.append(
            {
                "task_id": len(embedding_rows),
                "dataset": dataset,
                "union_json": str(union_json),
                "model_url": MODEL_URL,
                "embedding_pickle": str(union_dir / "miewid_union_embeddings.pickle"),
                "run_log": str(union_dir / "miewid_union.log"),
                "num_annotations": len(annotations),
            }
        )

    args.embedding_manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.embedding_manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=embedding_rows[0].keys(),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(embedding_rows)

    print(f"Built {len(embedding_rows)} embedding unions.")
    print(f"Total unique annotations: {sum(row['num_annotations'] for row in embedding_rows)}")
    for row in embedding_rows:
        print(f"  {row['dataset']}: {row['num_annotations']}")
    print(f"Embedding manifest: {args.embedding_manifest.resolve()}")


if __name__ == "__main__":
    main()
