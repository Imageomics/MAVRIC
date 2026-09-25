import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from VAREID.algo.postprocessing import postprocessing


def annotation(uuid, tracking_id, cluster_id, viewpoint):
    return {
        "uuid": uuid,
        "image_uuid": f"image-{uuid}",
        "bbox": [0, 0, 10, 10],
        "tracking_id": tracking_id,
        "category_id": 0,
        "viewpoint": viewpoint,
        "CA_score": 0.9,
        "LCA_clustering_id": cluster_id,
    }


def dataset(annotations):
    return {
        "categories": [{"id": 0, "species": "test species"}],
        "images": [
            {
                "uuid": item["image_uuid"],
                "image_path": f"/{item['image_uuid']}.jpg",
            }
            for item in annotations
        ],
        "annotations": annotations,
    }


class PostprocessingSplitRegressionTests(unittest.TestCase):
    def run_postprocessing(self, left_annotations, right_annotations):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            in_left = root / "in_left.json"
            in_right = root / "in_right.json"
            out_left = root / "out_left.json"
            out_right = root / "out_right.json"
            in_left.write_text(
                json.dumps(dataset(left_annotations)), encoding="utf-8"
            )
            in_right.write_text(
                json.dumps(dataset(right_annotations)), encoding="utf-8"
            )

            argv = [
                "postprocessing.py",
                str(root),
                str(in_left),
                str(in_right),
                str(out_left),
                str(out_right),
                "--interaction_mode",
                "console",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    postprocessing,
                    "pairwise_verification_interactive",
                    return_value="No",
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                postprocessing.main()

            return (
                json.loads(out_left.read_text(encoding="utf-8")),
                json.loads(out_right.read_text(encoding="utf-8")),
            )

    def test_nested_split_cluster_key_preserves_right_view_annotations(self):
        left, right = self.run_postprocessing(
            [
                annotation("left-one", 1, "8", "left"),
                annotation("left-two", 2, "9", "left"),
            ],
            [
                annotation("right-one", 1, "3_split1", "right"),
                annotation("right-two", 2, "3_split1", "right"),
            ],
        )

        output_annotations = left["annotations"] + right["annotations"]
        self.assertEqual(
            {item["uuid"] for item in output_annotations},
            {"left-one", "left-two", "right-one", "right-two"},
        )
        self.assertEqual(
            {item["uuid"] for item in right["annotations"]},
            {"right-one", "right-two"},
        )
        self.assertEqual(
            {item["LCA_clustering_id"] for item in right["annotations"]},
            {"3_split1_split1", "3_split1_split2"},
        )

    def test_automatic_splits_refresh_stale_cross_view_conflicts(self):
        left, right = self.run_postprocessing(
            [
                annotation("left-one", 1, "10", "left"),
                annotation("left-two", 2, "10", "left"),
                annotation("left-three", 3, "11", "left"),
            ],
            [
                annotation("right-one", 1, "20", "right"),
                annotation("right-three", 3, "20", "right"),
                annotation("right-two", 2, "21", "right"),
            ],
        )

        output_annotations = left["annotations"] + right["annotations"]
        self.assertEqual(
            {item["uuid"] for item in output_annotations},
            {
                "left-one",
                "left-two",
                "left-three",
                "right-one",
                "right-two",
                "right-three",
            },
        )

        grouped = {
            **postprocessing.group_annotations_by_lca_with_viewpoint(left, "left"),
            **postprocessing.group_annotations_by_lca_with_viewpoint(right, "right"),
        }
        conflicts = postprocessing.find_conflicts(
            postprocessing.check_numeric_equivalence(grouped)
        )
        self.assertEqual(conflicts, {})


if __name__ == "__main__":
    unittest.main()
