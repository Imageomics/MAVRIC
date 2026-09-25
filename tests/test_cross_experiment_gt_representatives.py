import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ablation.cross_experiment.build_gt_representative_bundles import (
    select_gt_representatives,
)


def annotation(uuid, image_uuid, viewpoint, tracking_id, score, category_id=7):
    return {
        "uuid": uuid,
        "image_uuid": image_uuid,
        "viewpoint": viewpoint,
        "tracking_id": tracking_id,
        "category_id": category_id,
        "bbox": [0, 0, 10, 10],
        "CA_score": score,
    }


def write_source(root, experiment, annotations, category_id=7):
    source_dir = root / experiment
    source_dir.mkdir()
    data = {
        "categories": [{"id": category_id, "species": "plains zebra"}],
        "images": [
            {
                "uuid": annotation["image_uuid"],
                "image_path": f"/{annotation['image_uuid']}.jpg",
                "frame_number": index + 1,
            }
            for index, annotation in enumerate(annotations)
        ],
        "annotations": annotations,
    }
    fs_json = source_dir / "fs_annots.json"
    embedding_pickle = source_dir / "embeddings.pickle"
    fs_json.write_text(json.dumps(data), encoding="utf-8")
    embeddings = np.asarray(
        [[float(index), float(index + 100)] for index in range(len(annotations))]
    )
    with embedding_pickle.open("wb") as file:
        pickle.dump((embeddings, [a["uuid"] for a in annotations]), file)
    return {
        "name": experiment,
        "fs_json": fs_json,
        "embedding_pickle": embedding_pickle,
    }


class GTRepresentativeBundleTests(unittest.TestCase):
    def test_selects_highest_ca_per_identity_viewpoint_and_excludes_non_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_source(
                root,
                "Plains_Experiment_7",
                [
                    annotation("left-19", "image-1", "left", 19, 0.70),
                    annotation("left-83", "image-2", "left", 83, 0.90),
                    annotation("right-19", "image-3", "right", 19, 0.80),
                    annotation("right-52", "image-4", "right", 52, 0.95),
                    annotation("non-id", "image-5", "left", 99, 0.99),
                ],
            )
            second = write_source(
                root,
                "Plains_Experiment_8",
                [annotation("second-left", "image-6", "left", 19, 0.85)],
            )
            ground_truth = {
                "Plains_Experiment_7": {
                    "individuals": [
                        {"id": 4, "left": [19, 83], "right": [19, 52]}
                    ]
                },
                "Plains_Experiment_8": {
                    "individuals": [{"id": 4, "left": [19], "right": []}]
                },
            }

            bundle, embeddings, identities, selections, sources = (
                select_gt_representatives(
                    "plains",
                    ["plains zebra"],
                    [first, second],
                    ground_truth,
                )
            )

        self.assertEqual(
            [a["uuid"] for a in bundle["annotations"]],
            ["left-83", "right-52", "second-left"],
        )
        self.assertEqual([a["tracking_id"] for a in bundle["annotations"]], [1, 1, 2])
        self.assertEqual(
            [a["original_tracking_id"] for a in bundle["annotations"]],
            [83, 52, 19],
        )
        self.assertEqual(
            bundle["annotations"][0]["source_candidate_tracking_ids"],
            [19, 83],
        )
        self.assertEqual(
            [a["source_ground_truth_id"] for a in bundle["annotations"]],
            [4, 4, 4],
        )
        self.assertEqual(len(identities), 2)
        self.assertEqual(len(selections), 3)
        self.assertEqual(embeddings[1], ["left-83", "right-52", "second-left"])
        np.testing.assert_array_equal(
            embeddings[0],
            np.asarray([[1.0, 101.0], [3.0, 103.0], [0.0, 100.0]]),
        )
        self.assertEqual(sources[0]["non_id_annotations"], 1)

    def test_rejects_missing_gt_tid(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_source(
                Path(directory),
                "Plains_Experiment_7",
                [annotation("left-19", "image-1", "left", 19, 0.70)],
            )
            ground_truth = {
                "Plains_Experiment_7": {
                    "individuals": [{"id": 1, "left": [20], "right": []}]
                }
            }

            with self.assertRaisesRegex(ValueError, "missing left TID 20"):
                select_gt_representatives(
                    "plains", ["plains zebra"], [source], ground_truth
                )

    def test_rejects_cross_view_tid_linked_to_different_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_source(
                Path(directory),
                "Plains_Experiment_7",
                [
                    annotation("left-19", "image-1", "left", 19, 0.70),
                    annotation("right-19", "image-2", "right", 19, 0.80),
                ],
            )
            ground_truth = {
                "Plains_Experiment_7": {
                    "individuals": [
                        {"id": 1, "left": [19], "right": []},
                        {"id": 2, "left": [], "right": [19]},
                    ]
                }
            }

            with self.assertRaisesRegex(ValueError, "different cross-view identities"):
                select_gt_representatives(
                    "plains", ["plains zebra"], [source], ground_truth
                )


if __name__ == "__main__":
    unittest.main()
