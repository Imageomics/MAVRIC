#!/usr/bin/env python3
"""Filter an IA35 annotation JSON at a stricter CA-score threshold."""

import argparse
import json
import os
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("threshold", type=float)
    return parser.parse_args()


def filter_ia_data(data, threshold):
    if not 0.35 < threshold < 1.0:
        raise ValueError(f"Threshold must be between 0.35 and 1.0, received {threshold}.")

    source_annotations = data.get("annotations", [])
    missing_uuids = [
        index
        for index, annotation in enumerate(source_annotations)
        if annotation.get("uuid") is None
    ]
    if missing_uuids:
        raise ValueError(
            f"{len(missing_uuids)} annotations have no UUID; indices: {missing_uuids[:5]}"
        )

    missing_scores = [
        annotation.get("uuid", "<missing uuid>")
        for annotation in source_annotations
        if annotation.get("CA_score") is None
    ]
    if missing_scores:
        raise ValueError(
            f"{len(missing_scores)} annotations have no CA_score; examples: "
            f"{missing_scores[:5]}"
        )

    annotations = [
        annotation
        for annotation in source_annotations
        if float(annotation["CA_score"]) > threshold
    ]
    missing_image_uuids = [
        annotation["uuid"]
        for annotation in annotations
        if annotation.get("image_uuid") is None
    ]
    if missing_image_uuids:
        raise ValueError(
            f"{len(missing_image_uuids)} retained annotations have no image_uuid; "
            f"examples: {missing_image_uuids[:5]}"
        )

    annotation_uuids = [annotation.get("uuid") for annotation in annotations]
    if len(annotation_uuids) != len(set(annotation_uuids)):
        raise ValueError("Filtered annotations contain duplicate UUIDs.")

    referenced_images = {annotation["image_uuid"] for annotation in annotations}
    images = [
        image for image in data.get("images", []) if image.get("uuid") in referenced_images
    ]
    found_images = {image.get("uuid") for image in images}
    missing_images = referenced_images - found_images
    if missing_images:
        raise ValueError(
            f"Filtered annotations reference {len(missing_images)} missing images; "
            f"examples: {sorted(missing_images)[:5]}"
        )

    return {
        "categories": data.get("categories", []),
        "images": images,
        "annotations": annotations,
    }


def save_json_atomic(data, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as file:
        temporary_path = Path(file.name)
        json.dump(data, file, indent=2)
        file.write("\n")
    os.replace(temporary_path, output_path)


def main():
    args = parse_args()
    with args.source_json.open("r", encoding="utf-8") as file:
        source = json.load(file)

    filtered = filter_ia_data(source, args.threshold)
    if not filtered["annotations"]:
        raise ValueError(
            f"No annotations remain after applying CA_score > {args.threshold:.2f}."
        )
    save_json_atomic(filtered, args.output_json)

    source_tracks = {
        annotation.get("tracking_id") for annotation in source.get("annotations", [])
    }
    filtered_tracks = {
        annotation.get("tracking_id") for annotation in filtered["annotations"]
    }
    print(f"Filtering rule: CA_score > {args.threshold:.2f}")
    print(f"Source annotations: {len(source.get('annotations', []))}")
    print(f"Retained annotations: {len(filtered['annotations'])}")
    print(f"Source tracking IDs: {len(source_tracks)}")
    print(f"Retained tracking IDs: {len(filtered_tracks)}")
    print(f"Saved: {args.output_json}")


if __name__ == "__main__":
    main()
