import unittest

from ablation.cross_experiment.project_ground_truth import project_ground_truth


class CrossExperimentGroundTruthProjectionTests(unittest.TestCase):
    def test_projects_identity_clusters_without_changing_pipeline_track_ids(self):
        mapping_rows = [
            {
                "source_experiment": "Giraffe_Experiment_12",
                "original_tracking_id": 9,
                "global_tracking_id": 101,
                "viewpoints": "left",
            },
            {
                "source_experiment": "Giraffe_Experiment_13",
                "original_tracking_id": 517,
                "global_tracking_id": 202,
                "viewpoints": "left,right",
            },
            {
                "source_experiment": "Giraffe_Experiment_13",
                "original_tracking_id": 999,
                "global_tracking_id": 203,
                "viewpoints": "right",
            },
        ]
        within_session_ground_truth = {
            "experiments": {
                "Giraffe_Experiment_12": {
                    "individuals": [{"id": 3, "left": [9, 84], "right": []}]
                },
                "Giraffe_Experiment_13": {
                    "individuals": [
                        {"id": 3, "left": [517], "right": [517]}
                    ]
                },
            }
        }
        cross_session_ground_truth = {
            "individuals": [{"id": 7, "left": [3, 13], "right": [13]}]
        }
        source_identity_map = {
            3: {
                "source_experiment": "Giraffe_Experiment_12",
                "source_ground_truth_id": 3,
            },
            13: {
                "source_experiment": "Giraffe_Experiment_13",
                "source_ground_truth_id": 3,
            },
        }

        projection, labeled, unlabeled, missing = project_ground_truth(
            "giraffes",
            0.75,
            mapping_rows,
            within_session_ground_truth,
            cross_session_ground_truth,
            source_identity_map,
        )

        self.assertEqual(projection["individuals"][0]["id"], 7)
        self.assertEqual(projection["individuals"][0]["left"], [101, 202])
        self.assertEqual(projection["individuals"][0]["right"], [202])
        self.assertEqual({row["global_tracking_id"] for row in labeled}, {101, 202})
        self.assertEqual([row["global_tracking_id"] for row in unlabeled], [203])
        self.assertEqual([row["original_tracking_id"] for row in missing], [84])


if __name__ == "__main__":
    unittest.main()
