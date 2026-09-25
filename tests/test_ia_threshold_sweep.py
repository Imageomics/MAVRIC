import unittest
import pickle
import tempfile
from pathlib import Path

import numpy as np

from ablation.ia_threshold.build_embedding_unions import build_union
from ablation.ia_threshold.filter_ia import filter_ia_data
from ablation.ia_threshold.generate_sweep import (
    THRESHOLD_LABELS,
    build_rows,
    frame_sampling_config,
    output_paths,
)
from ablation.ia_threshold.validate_embedding_cache import validate_embedding_cache


def make_data():
    return {
        "categories": [{"id": 0, "species": "grevy's zebra"}],
        "images": [
            {"uuid": "image-1", "image_path": "/tmp/image-1.jpg"},
            {"uuid": "image-2", "image_path": "/tmp/image-2.jpg"},
            {"uuid": "unused-image", "image_path": "/tmp/unused.jpg"},
        ],
        "annotations": [
            {
                "uuid": "equal",
                "image_uuid": "image-1",
                "tracking_id": 1,
                "CA_score": 0.40,
            },
            {
                "uuid": "above",
                "image_uuid": "image-2",
                "tracking_id": 2,
                "CA_score": 0.40001,
            },
        ],
    }


class IAThresholdFilteringTests(unittest.TestCase):
    def test_filter_uses_pipeline_strict_greater_than_semantics(self):
        filtered = filter_ia_data(make_data(), 0.40)

        self.assertEqual(
            [annotation["uuid"] for annotation in filtered["annotations"]],
            ["above"],
        )

    def test_filter_prunes_unreferenced_images(self):
        filtered = filter_ia_data(make_data(), 0.40)

        self.assertEqual(
            [image["uuid"] for image in filtered["images"]],
            ["image-2"],
        )

    def test_filter_rejects_missing_scores(self):
        data = make_data()
        data["annotations"][0]["CA_score"] = None

        with self.assertRaisesRegex(ValueError, "no CA_score"):
            filter_ia_data(data, 0.40)

    def test_filter_rejects_missing_image_records(self):
        data = make_data()
        data["images"] = []

        with self.assertRaisesRegex(ValueError, "missing images"):
            filter_ia_data(data, 0.40)

    def test_embedding_union_preserves_source_annotation_order(self):
        union = build_union(make_data(), {"equal", "above"}, "test")

        self.assertEqual(
            [annotation["uuid"] for annotation in union["annotations"]],
            ["equal", "above"],
        )
        self.assertNotIn(
            "unused-image",
            {image["uuid"] for image in union["images"]},
        )

    def test_embedding_cache_validation_checks_uuid_order(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            union_path = directory / "union.json"
            pickle_path = directory / "embeddings.pickle"
            union_path.write_text(
                '{"annotations": [{"uuid": "one"}, {"uuid": "two"}]}',
                encoding="utf-8",
            )
            with pickle_path.open("wb") as file:
                pickle.dump((np.zeros((2, 3)), ["one", "two"]), file)

            self.assertEqual(
                validate_embedding_cache(union_path, pickle_path),
                2,
            )


class IAThresholdManifestTests(unittest.TestCase):
    def test_threshold_grid_has_twelve_cells(self):
        self.assertEqual(THRESHOLD_LABELS, tuple(range(40, 100, 5)))

    def test_operating_point_is_fixed(self):
        config = frame_sampling_config(15)

        self.assertEqual(config["thresholds"]["t_seconds"], 5)
        self.assertEqual(config["thresholds"]["quality_threshold_pct"], 0.9)
        self.assertEqual(config["settings"]["selection_mode"], "many")
        self.assertEqual(config["settings"]["num_RA_annots"], 10)

    def test_output_path_is_nested_under_the_experiment(self):
        source = Path(
            "/results/Grevys_Experiment_1_test_mavric_imageomics/"
            "ia_classifier/ia_annots_filtered_35.json"
        )
        paths = output_paths("Grevys_Experiment_1", source, 40)

        self.assertEqual(
            paths["filtered_json"],
            Path(
                "/results/Grevys_Experiment_1_test_mavric_imageomics/"
                "Grevys_Experiment_1_IA_40/ia_classifier/"
                "ia_annots_filtered_40.json"
            ),
        )

    def test_thirteen_datasets_generate_156_tasks(self):
        datasets = [
            {
                "name": f"Dataset_{index}",
                "input_json": f"/results/Dataset_{index}/ia_classifier/source.json",
            }
            for index in range(13)
        ]

        rows = build_rows(datasets, Path("/configs/frame_sampling.yaml"))

        self.assertEqual(len(rows), 156)
        self.assertEqual(rows[0]["threshold"], "0.40")
        self.assertEqual(rows[-1]["threshold"], "0.95")


if __name__ == "__main__":
    unittest.main()
