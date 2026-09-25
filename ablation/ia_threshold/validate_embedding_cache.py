#!/usr/bin/env python3
"""Validate that a MiewID pickle exactly matches an annotation union JSON."""

import argparse
import json
import pickle
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("union_json", type=Path)
    parser.add_argument("embedding_pickle", type=Path)
    return parser.parse_args()


def validate_embedding_cache(union_json, embedding_pickle):
    with union_json.open("r", encoding="utf-8") as file:
        data = json.load(file)
    expected_uuids = [
        annotation["uuid"] for annotation in data.get("annotations", [])
    ]

    with embedding_pickle.open("rb") as file:
        embeddings, actual_uuids = pickle.load(file)
    actual_uuids = list(actual_uuids)
    if len(embeddings) != len(actual_uuids):
        raise ValueError("Embedding rows and cached UUIDs have different lengths.")
    if actual_uuids != expected_uuids:
        raise ValueError("Cached UUID order does not match the current union JSON.")
    return len(expected_uuids)


def main():
    args = parse_args()
    count = validate_embedding_cache(args.union_json, args.embedding_pickle)
    print(f"Validated {count} cached embeddings: {args.embedding_pickle}")


if __name__ == "__main__":
    main()
