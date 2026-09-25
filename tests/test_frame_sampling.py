import unittest

from VAREID.algo.frame_sampling.frame_sampling import (
    run_many_mode_logic,
    run_one_mode_logic,
)


def make_annotation(frame_number, score, tracking_id=1, viewpoint="left"):
    return {
        "uuid": f"ann-{viewpoint}-{tracking_id}-{frame_number}",
        "frame_number": frame_number,
        "tracking_id": tracking_id,
        "viewpoint": viewpoint,
        "CA_score": score,
    }


def make_config(t_seconds=15, frame_interval=15, quality=0.8, cap=5):
    return {
        "thresholds": {
            "t_seconds": t_seconds,
            "frame_interval": frame_interval,
            "quality_threshold_pct": quality,
        },
        "settings": {
            "num_RA_annots": cap,
            "use_viewpoint": True,
            "use_ca_score": True,
        },
    }


class ManyModeSamplingTests(unittest.TestCase):
    def test_monotonically_increasing_track_keeps_endpoint_global_best(self):
        annotations = [make_annotation(frame, frame / 10) for frame in range(1, 6)]

        selected = run_many_mode_logic(
            {"annotations": annotations},
            make_config(t_seconds=1, frame_interval=1),
        )

        self.assertEqual([ann["frame_number"] for ann in selected], [5])

    def test_first_frame_global_best_survives_quality_gate(self):
        annotations = [
            make_annotation(1, 1.0),
            make_annotation(2, 0.2),
            make_annotation(3, 0.1),
            make_annotation(4, 0.3),
        ]

        selected = run_many_mode_logic(
            {"annotations": annotations},
            make_config(t_seconds=1, frame_interval=1, quality=0.8),
        )

        self.assertEqual([ann["frame_number"] for ann in selected], [1])

    def test_every_nonempty_viewpoint_track_group_gets_a_representative(self):
        annotations = [
            make_annotation(1, 0.9, tracking_id=1, viewpoint="left"),
            make_annotation(2, 1.0, tracking_id=1, viewpoint="left"),
            make_annotation(1, 0.8, tracking_id=2, viewpoint="left"),
            make_annotation(2, 0.7, tracking_id=2, viewpoint="left"),
            make_annotation(1, None, tracking_id=1, viewpoint="right"),
            make_annotation(2, None, tracking_id=1, viewpoint="right"),
        ]

        selected = run_many_mode_logic(
            {"annotations": annotations},
            make_config(t_seconds=1, frame_interval=1),
        )
        selected_groups = {
            (ann["viewpoint"], ann["tracking_id"])
            for ann in selected
        }

        self.assertEqual(
            selected_groups,
            {("left", 1), ("left", 2), ("right", 1)},
        )

    def test_negative_tracking_sentinel_is_not_selected(self):
        annotations = [
            make_annotation(1, 1.0, tracking_id=-1, viewpoint="left"),
            make_annotation(2, 0.8, tracking_id=7, viewpoint="left"),
        ]

        selected = run_many_mode_logic(
            {"annotations": annotations},
            make_config(t_seconds=1, frame_interval=1),
        )

        self.assertEqual([ann["tracking_id"] for ann in selected], [7])


class OneModeSamplingTests(unittest.TestCase):
    def test_negative_tracking_sentinel_is_not_selected(self):
        annotations = [
            make_annotation(1, 1.0, tracking_id=-1, viewpoint="left"),
            make_annotation(2, 0.8, tracking_id=7, viewpoint="left"),
        ]

        selected = run_one_mode_logic(
            {"annotations": annotations},
            use_ca=True,
            use_vp=True,
        )

        self.assertEqual([ann["tracking_id"] for ann in selected], [7])


if __name__ == "__main__":
    unittest.main()
