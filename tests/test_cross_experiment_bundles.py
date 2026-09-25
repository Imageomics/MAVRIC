import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ablation.cross_experiment.build_bundles import combine_experiments


def write_source(root, experiment, annotations, category_id):
    source_dir = root / experiment
    source_dir.mkdir()
    image_uuids = {annotation["image_uuid"] for annotation in annotations}
    data = {
        "categories": [{"id": category_id, "species": "plains zebra"}],
        "images": [
            {"uuid": image_uuid, "image_path": f"/{image_uuid}.jpg"}
            for image_uuid in sorted(image_uuids)
        ],
        "annotations": annotations,
    }
    fs_json = source_dir / "fs_annots.json"
    embedding_pickle = source_dir / "embeddings.pickle"
    fs_json.write_text(json.dumps(data), encoding="utf-8")
    embeddings = np.asarray(
        [[float(index), float(index + 10)] for index in range(len(annotations))]
    )
    with embedding_pickle.open("wb") as file:
        pickle.dump((embeddings, [a["uuid"] for a in annotations]), file)
    return {
        "name": experiment,
        "fs_json": fs_json,
        "embedding_pickle": embedding_pickle,
    }


def annotation(uuid, image_uuid, viewpoint, tracking_id, category_id):
    return {
        "uuid": uuid,
        "image_uuid": image_uuid,
        "viewpoint": viewpoint,
        "tracking_id": tracking_id,
        "category_id": category_id,
        "bbox": [0, 0, 10, 10],
        "CA_score": 0.9,
    }


class CrossExperimentBundleTests(unittest.TestCase):
    def test_remapping_is_unique_across_experiments_and_reversible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_source(
                root,
                "Plains_Experiment_7",
                [
                    annotation("a-left", "i1", "left", 1, 4),
                    annotation("a-right", "i2", "right", 1, 4),
                    annotation("a-negative", "i3", "left", -1, 4),
                ],
                4,
            )
            second = write_source(
                root,
                "Plains_Experiment_8",
                [annotation("b-left", "i4", "left", 1, 9)],
                9,
            )

            bundle, embeddings, mappings, sources, excluded = combine_experiments(
                "plains",
                ["plains zebra"],
                [first, second],
            )

        self.assertEqual(
            [a["tracking_id"] for a in bundle["annotations"]],
            [1, 1, 2],
        )
        self.assertEqual(
            [a["original_tracking_id"] for a in bundle["annotations"]],
            [1, 1, 1],
        )
        self.assertEqual(
            [a["source_experiment"] for a in bundle["annotations"]],
            ["Plains_Experiment_7", "Plains_Experiment_7", "Plains_Experiment_8"],
        )
        self.assertEqual(
            [(m["source_experiment"], m["original_tracking_id"]) for m in mappings],
            [("Plains_Experiment_7", 1), ("Plains_Experiment_8", 1)],
        )
        self.assertEqual([m["global_tracking_id"] for m in mappings], [1, 2])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["annotation_uuid"], "a-negative")
        self.assertEqual(embeddings[1], ["a-left", "a-right", "b-left"])
        np.testing.assert_array_equal(
            embeddings[0],
            np.asarray([[0.0, 10.0], [1.0, 11.0], [0.0, 10.0]]),
        )
        self.assertEqual(sources[0]["excluded_negative_tid_annotations"], 1)
        self.assertEqual(bundle["categories"], [{"id": 0, "species": "plains zebra"}])

    def test_rejects_non_one_best_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_source(
                Path(directory),
                "Plains_Experiment_7",
                [
                    annotation("one", "i1", "left", 1, 0),
                    annotation("two", "i2", "left", 1, 0),
                ],
                0,
            )

            with self.assertRaisesRegex(ValueError, "not one-best"):
                combine_experiments("plains", ["plains zebra"], [source])

    def test_many_mode_preserves_multiple_ras_and_uses_stable_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_source(
                Path(directory),
                "Plains_Experiment_7",
                [
                    annotation("one", "i1", "left", 9, 0),
                    annotation("two", "i2", "left", 9, 0),
                    annotation("three", "i3", "right", 9, 0),
                ],
                0,
            )

            bundle, embeddings, mappings, _, _ = combine_experiments(
                "plains",
                ["plains zebra"],
                [source],
                selection_mode="many",
                global_tid_registry={("Plains_Experiment_7", 9): 42},
            )

        self.assertEqual([a["tracking_id"] for a in bundle["annotations"]], [42] * 3)
        self.assertEqual([a["original_tracking_id"] for a in bundle["annotations"]], [9] * 3)
        self.assertEqual(mappings[0]["global_tracking_id"], 42)
        self.assertEqual(mappings[0]["annotation_count"], 3)
        self.assertEqual(embeddings[1], ["one", "two", "three"])

    def test_rejects_embedding_uuid_order_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_source(
                root,
                "Plains_Experiment_7",
                [
                    annotation("one", "i1", "left", 1, 0),
                    annotation("two", "i2", "right", 1, 0),
                ],
                0,
            )
            with source["embedding_pickle"].open("rb") as file:
                embeddings, uuids = pickle.load(file)
            with source["embedding_pickle"].open("wb") as file:
                pickle.dump((embeddings, list(reversed(uuids))), file)

            with self.assertRaisesRegex(ValueError, "UUID order"):
                combine_experiments("plains", ["plains zebra"], [source])


if __name__ == "__main__":
    unittest.main()
