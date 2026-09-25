#!/usr/bin/env python3
"""Summarize RA counts and identify parameter cells with identical selections."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=SCRIPT_DIR / "generated" / "manifest.tsv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SCRIPT_DIR / "generated" / "selection_summary.csv",
    )
    return parser.parse_args()


def selection_key(annotation):
    return str(
        annotation.get("uuid")
        or (
            annotation.get("image_uuid"),
            annotation.get("tracking_id"),
            annotation.get("viewpoint"),
        )
    )


def main():
    args = parse_args()
    with args.manifest.open("r", encoding="utf-8", newline="") as file:
        manifest = list(csv.DictReader(file, delimiter="\t"))

    rows = []
    first_by_dataset_hash = {}
    groups = defaultdict(list)

    for task in manifest:
        output_path = Path(task["output_json"])
        if not output_path.is_file():
            rows.append({**task, "status": "missing", "num_annotations": "", "selection_hash": "", "duplicate_of": ""})
            continue

        with output_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        keys = sorted(selection_key(annotation) for annotation in data.get("annotations", []))
        digest = hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()
        group_key = (task["dataset"], digest)
        duplicate_of = first_by_dataset_hash.setdefault(group_key, task["run_name"])
        groups[group_key].append(task["run_name"])
        rows.append(
            {
                **task,
                "status": "complete",
                "num_annotations": len(keys),
                "selection_hash": digest,
                "duplicate_of": "" if duplicate_of == task["run_name"] else duplicate_of,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    complete = sum(row["status"] == "complete" for row in rows)
    collapsed = sum(len(run_names) - 1 for run_names in groups.values())
    print(f"Complete outputs: {complete}/{len(rows)}")
    print(f"Collapsed duplicate cells: {collapsed}")
    print(f"Summary: {args.output.resolve()}")


if __name__ == "__main__":
    main()
