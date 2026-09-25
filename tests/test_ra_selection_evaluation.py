import unittest
import json
import pickle
import tempfile
from pathlib import Path

import numpy as np

from ablation.ra_selection.evaluate_sweep import (
    average_precision_at_k,
    fixed_query_metrics,
    retrieval_metrics,
)
from ablation.ra_selection.materialize_selected_embeddings import materialize


class RetrievalMetricTests(unittest.TestCase):
    def test_standard_ap_penalizes_missing_relevant_items(self):
        self.assertAlmostEqual(
            average_precision_at_k([True, False], total_relevant=2, k=2),
            0.5,
        )

    def test_paper_compatible_ap_normalizes_by_retrieved_hits(self):
        self.assertAlmostEqual(
            average_precision_at_k(
                [True, False],
                total_relevant=2,
                k=2,
                paper_compatible=True,
            ),
            1.0,
        )

    def test_strict_metric_excludes_same_tid_gallery_items(self):
        embeddings = np.asarray(
            [
                [1.0, 0.0],
                [0.99, 0.01],
                [0.0, 1.0],
                [0.8, 0.6],
            ]
        )
        metadata = [
            {"identity": 1, "viewpoint": "left", "tracking_id": 10},
            {"identity": 1, "viewpoint": "left", "tracking_id": 10},
            {"identity": 1, "viewpoint": "left", "tracking_id": 20},
            {"identity": 2, "viewpoint": "left", "tracking_id": 30},
        ]

        paper = retrieval_metrics(embeddings, metadata, k=1, exclude_same_tid=False)
        strict = retrieval_metrics(embeddings, metadata, k=1, exclude_same_tid=True)

        self.assertGreater(paper["map"], strict["map"])
        self.assertEqual(strict["queries"], 3)

    def test_fixed_queries_do_not_change_when_gallery_lacks_positives(self):
        query_embeddings = np.asarray([[1.0, 0.0], [0.9, 0.1]])
        query_metadata = [
            {"identity": 1, "viewpoint": "left", "tracking_id": 10},
            {"identity": 1, "viewpoint": "left", "tracking_id": 20},
        ]
        gt_map = {("left", 10): 1, ("left", 20): 1}

        result = fixed_query_metrics(
            query_embeddings,
            query_metadata,
            np.asarray([[0.0, 1.0]]),
            [{"identity": 2, "viewpoint": "left", "tracking_id": 30}],
            gt_map,
            k=1,
        )

        self.assertEqual(result["queries"], 2)
        self.assertEqual(result["map"], 0.0)

    def test_fixed_query_metric_excludes_single_track_identities(self):
        result = fixed_query_metrics(
            np.asarray([[1.0, 0.0], [0.0, 1.0]]),
            [
                {"identity": 1, "viewpoint": "left", "tracking_id": 10},
                {"identity": 2, "viewpoint": "left", "tracking_id": 30},
            ],
            np.asarray([[0.9, 0.1], [0.1, 0.9]]),
            [
                {"identity": 1, "viewpoint": "left", "tracking_id": 20},
                {"identity": 2, "viewpoint": "left", "tracking_id": 40},
            ],
            {
                ("left", 10): 1,
                ("left", 20): 1,
                ("left", 30): 2,
            },
            k=1,
        )

        self.assertEqual(result["queries"], 1)
        self.assertEqual(result["map"], 1.0)


class SelectedEmbeddingTests(unittest.TestCase):
    def test_materialize_preserves_selection_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            selected_path = root / "selected.json"
            union_path = root / "union.pickle"
            output_path = root / "selected.pickle"
            selected_path.write_text(
                json.dumps(
                    {
                        "annotations": [
                            {"uuid": "ann-c"},
                            {"uuid": "ann-a"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with union_path.open("wb") as file:
                pickle.dump(
                    (
                        np.asarray([[1, 0], [0, 1], [2, 2]]),
                        ["ann-a", "ann-b", "ann-c"],
                    ),
                    file,
                )

            count = materialize(selected_path, union_path, output_path)

            with output_path.open("rb") as file:
                embeddings, uuids = pickle.load(file)
            self.assertEqual(count, 2)
            self.assertEqual(uuids, ["ann-c", "ann-a"])
            np.testing.assert_array_equal(embeddings, [[2, 2], [1, 0]])


if __name__ == "__main__":
    unittest.main()
