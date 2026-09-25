#!/usr/bin/env python3
"""Subset a union embedding cache to one frame-sampling selection."""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selected_json", type=Path)
    parser.add_argument("union_pickle", type=Path)
    parser.add_argument("output_pickle", type=Path)
    return parser.parse_args()


def materialize(selected_json, union_pickle, output_pickle):
    with selected_json.open("r", encoding="utf-8") as file:
        selected = json.load(file)
    selected_uuids = [annotation["uuid"] for annotation in selected["annotations"]]
    if len(selected_uuids) != len(set(selected_uuids)):
        raise ValueError(f"Selection contains duplicate UUIDs: {selected_json}")

    with union_pickle.open("rb") as file:
        embeddings, union_uuids = pickle.load(file)
    embeddings = np.asarray(embeddings)
    union_uuids = list(union_uuids)
    if len(embeddings) != len(union_uuids):
        raise ValueError(f"Union embedding/UUID mismatch: {union_pickle}")
    if len(union_uuids) != len(set(union_uuids)):
        raise ValueError(f"Union cache contains duplicate UUIDs: {union_pickle}")

    index_by_uuid = {uuid: index for index, uuid in enumerate(union_uuids)}
    missing = [uuid for uuid in selected_uuids if uuid not in index_by_uuid]
    if missing:
        raise KeyError(
            f"{len(missing)} selected UUIDs are absent from {union_pickle}: "
            f"{missing[:5]}"
        )

    selected_embeddings = np.asarray(
        [embeddings[index_by_uuid[uuid]] for uuid in selected_uuids]
    )
    output_pickle.parent.mkdir(parents=True, exist_ok=True)
    with output_pickle.open("wb") as file:
        pickle.dump((selected_embeddings, selected_uuids), file)

    return len(selected_uuids)


def main():
    args = parse_args()
    count = materialize(
        args.selected_json,
        args.union_pickle,
        args.output_pickle,
    )
    print(f"Materialized {count} selected embeddings: {args.output_pickle}")


if __name__ == "__main__":
    main()
