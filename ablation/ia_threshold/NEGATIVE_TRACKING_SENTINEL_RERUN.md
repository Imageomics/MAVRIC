# Per-session rerun after negative tracking-sentinel cleanup

On 2026-08-25, selected annotations with negative tracker sentinel ID `-1`
were removed from the per-session RA inputs and their aligned MiewID embedding
pickles. These detections do not form valid tracks and must not enter Beta
Stability or Tracking-Based Identity Resolution.

The exact 44 affected session/threshold inputs, before/after counts, UUIDs,
paths, and backup paths are recorded in:

```text
ablation/ia_threshold/generated/negative_tracking_id_cleanup.tsv
```

All 169 per-session JSON/pickle pairs were subsequently validated: UUID order,
annotation counts, embedding counts, metadata, and generated manifests agree,
and no selected negative tracking IDs remain.

## Reruns required

Use the same ground-truth-response Beta Stability configuration and the same
Tracking-Based Identity Resolution procedure used for the manuscript. For each
entry below, rerun:

1. Beta Stability;
2. Tracking-Based Identity Resolution;
3. track- and individual-ID metrics;
4. Beta/final-stage human-review aggregation.

Affected runs:

- `Grevys_Experiment_1`: 0.35, 0.40, 0.45, 0.50, 0.55, 0.60.
- `Plains_Experiment_7`: 0.35 and every threshold from 0.40 through 0.95.
- `Plains_Experiment_9`: 0.35 and every threshold from 0.40 through 0.90.
  Its 0.95 input was not affected.
- `Plains_Experiment_11`: 0.35 and every threshold from 0.40 through 0.95.

At the manuscript operating point, 0.75, rerun only Plains sessions 7, 9,
and 11. Their selected left/right RA counts are now:

| Session | Before | After |
| --- | ---: | ---: |
| Plains 7 | 67/20 | 66/20 |
| Plains 9 | 179/5 | 178/5 |
| Plains 11 | 83/99 | 82/99 |

Consequently, the deterministic exhaustive same-view baseline at 0.75 changes
from 55,924 to 55,598 RA-pair comparisons. Beta Stability and final-stage
review counts and accuracy metrics must come from the reruns; they cannot be
corrected arithmetically.

## Clean input paths

For 0.35, each clean input pair is:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  RA_selection_ablation_15fps/<dataset>/many_t05_q90_n10/
    fs_annots.json
    miewid_embeddings.pickle
```

For thresholds 0.40--0.95, each clean input pair is:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  <dataset>_test_mavric_imageomics/<dataset>_IA_<label>/
    frame_sampling/fs_annots.json
    miew_id/miewid_embeddings.pickle
```

The old downstream `lca_stability_universal_gthuman*` directories under the
affected 0.40--0.95 experiment roots predate this cleanup. The manuscript's
selected Beta configuration must be regenerated in a fresh directory or must
explicitly overwrite its old output so that an existence check does not skip
the run.

Detection, tracking, species/viewpoint prediction, IA scoring, threshold
filtering, RA selection, and MiewID embedding do not need to be rerun. The
cleaned per-session inputs already contain the correct aligned embeddings.

## Cross-session scope

Do not rerun or rebuild the pooled cross-session experiments for this cleanup.
Both the 0.35 and 0.75 pooled builders had already excluded negative tracking
sentinels. Their inputs remain aligned and unchanged.

## Recovery

Original modified inputs and manifests are preserved at:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  negative_tracking_id_cleanup_backup_20260825/
```
