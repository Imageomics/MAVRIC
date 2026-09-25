# IA Threshold Sweep

This workflow prepares threshold-specific, pre-LCA artifacts for all 13
canonical 15 fps experiments. It varies only the absolute identifiable-
annotation (IA) cutoff and keeps the selected frame-sampling operating point
fixed.

## Sweep Definition

- IA thresholds: `0.40, 0.45, ..., 0.95`
- Filtering rule: `CA_score > threshold`, matching `IA_classifier.py`
- Frame interval: `15`
- Frame-sampling mode: `many`
- Temporal spacing: `t_seconds = 5`
- Relative quality gate: `quality_threshold_pct = 0.9`
- Representative cap: `num_RA_annots = 10`
- MiewID model: `conservationxlabs/miewid-msv3`

The source for every threshold is the corresponding
`ia_classifier/ia_annots_filtered_35.json`. Import, detection/tracking,
species classification, viewpoint classification, IA inference, aspect-ratio
filtering, and IA NMS are not rerun. Score-ordered NMS makes a higher-threshold
result obtainable by filtering the IA35 result: a lower-scoring annotation
cannot suppress a retained higher-scoring annotation.

LCA is intentionally not run by this workflow.

## Output Layout

Each threshold is isolated inside its canonical experiment root. For example:

```text
Grevys_Experiment_1_test_mavric_imageomics/
  Grevys_Experiment_1_IA_40/
    ia_classifier/
      ia_annots_filtered_40.json
    frame_sampling/
      frame_sampling_config.yaml
      fs_annots.json
    miew_id/
      miewid_embeddings.pickle
    logs/
      ia_filtering.log
      frame_sampling.log
    metadata.yaml
```

One internal embedding cache is also created per experiment:

```text
Grevys_Experiment_1_IA_threshold_embedding_union/
  union_fs_annots.json
  miewid_union_embeddings.pickle
  miewid_union.log
```

## Generate Tasks

From the repository root:

```bash
python ablation/ia_threshold/generate_sweep.py
```

This validates all 13 IA35 inputs and creates an immutable frame-sampling
config plus a 156-row task manifest under `ablation/ia_threshold/generated/`.

## Submit

Submit the complete dependency chain with:

```bash
bash /users/PAS2136/upadha2/mavric-video-pipeline/ablation/ia_threshold/submit_sweep.sh
```

The chain performs:

1. IA filtering and frame sampling: 156 CPU array tasks.
2. Embedding-union construction: one CPU task.
3. MiewID inference: 13 GPU array tasks on `quad`.
4. Threshold-specific embedding materialization and metadata: one CPU task.

Jobs are connected with `afterok`, so a downstream stage starts only after all
tasks in its prerequisite stage succeed. Existing nonempty frame-sampling and
embedding outputs are skipped when a job is resubmitted.

The final inventory is written to:

```text
ablation/ia_threshold/generated/pre_lca_manifest.tsv
```

## Scientific Controls

- The global `IA_classifier_config.yaml` is never changed.
- Every threshold uses the same IA35 source and frame-sampling configuration.
- The 30 fps diagnostic experiments are excluded.
- Annotation/image references and UUID uniqueness are validated while filtering.
- Final embedding UUID order is validated against each `fs_annots.json`.
- Very high thresholds may leave too few cross-track positives for retrieval
  metrics; this is a valid sweep outcome rather than a pipeline failure.

## Negative tracking sentinels

Negative tracker IDs denote detections that do not belong to valid tracks and
are now excluded during RA selection. Historical selected inputs were cleaned
on 2026-08-25. See `NEGATIVE_TRACKING_SENTINEL_RERUN.md` for the affected
session/threshold runs, clean input paths, backups, and downstream rerun scope.
