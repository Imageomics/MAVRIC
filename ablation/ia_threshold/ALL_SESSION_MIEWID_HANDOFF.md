# Complete handoff for the clean per-session reruns

**Prepared:** 2026-08-25
**Scope:** all within-session experiments, from the existing selected
Representative Annotations (RAs) and MiewID embeddings onward
**Number of runs:** 13 sessions × 13 active/inactive thresholds = **169**
**Cross-session experiments:** explicitly out of scope; leave them unchanged

This is the complete input handoff for the coauthor running the downstream
identity-grouping experiments. All required work through MiewID has already
been completed and validated. The coauthor should start each run from the
paired annotation JSON and MiewID pickle specified below. There is no need to
rerun video processing, detection, tracking, species classification,
viewpoint classification, IA scoring, threshold filtering, RA selection, or
MiewID embedding.

This document intentionally does **not** prescribe the Beta Stability or
Tracking-Based Identity Resolution implementation. The coauthor responsible
for those stages should use their established downstream runner, but must use
the clean input pairs and the complete rerun scope defined here.

## 1. Required action

Run every one of the 169 within-session cases listed by the Cartesian product
of the following sessions and thresholds.

### Sessions

| Session index | Species | Exact dataset identifier |
|---:|---|---|
| 1 | Grevy's zebra | `Grevys_Experiment_1` |
| 2 | Grevy's zebra | `Grevys_Experiment_2` |
| 3 | Grevy's zebra | `Grevys_Experiment_3` |
| 4 | Grevy's zebra | `Grevys_Experiment_4` |
| 5 | Grevy's zebra | `Grevys_Experiment_5` |
| 6 | Grevy's zebra | `Grevys_Experiment_6` |
| 7 | Plains zebra | `Plains_Experiment_7` |
| 8 | Plains zebra | `Plains_Experiment_8` |
| 9 | Plains zebra | `Plains_Experiment_9` |
| 10 | Plains zebra | `Plains_Experiment_10` |
| 11 | Plains zebra | `Plains_Experiment_11` |
| 12 | Reticulated giraffe | `Giraffe_Experiment_12` |
| 13 | Reticulated giraffe | `Giraffe_Experiment_13` |

### Thresholds and directory labels

| Active/inactive threshold | Directory label |
|---:|---:|
| 0.35 | `35` |
| 0.40 | `40` |
| 0.45 | `45` |
| 0.50 | `50` |
| 0.55 | `55` |
| 0.60 | `60` |
| 0.65 | `65` |
| 0.70 | `70` |
| 0.75 | `75` |
| 0.80 | `80` |
| 0.85 | `85` |
| 0.90 | `90` |
| 0.95 | `95` |

The 0.35 case is included so the plots can begin at the ground-truth
candidate threshold. It uses the same many-RA inference policy as the other
thresholds; it is not the one-RA ground-truth curation selection.

## 2. Fixed upstream settings already applied

Every handed-off run uses the many-RA policy with these saved settings:

```yaml
thresholds:
  t_seconds: 5
  quality_threshold_pct: 0.9
  frame_interval: 15
settings:
  selection_mode: many
  num_RA_annots: 10
  use_ca_score: true
  use_viewpoint: true
  seed: 123456789
```

The run-name shorthand for this policy is `many_t05_q90_n10`. MiewID
embeddings were produced with `conservationxlabs/miewid-msv3`.

Do not substitute a one-RA input, a different RA policy, or a pooled
cross-session input.

## 3. Exact clean input paths

The common result root is:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth
```

### Threshold 0.35

For each exact dataset identifier `<DATASET>` in the session table, use this
pair:

```text
Annotation JSON:
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/<DATASET>/many_t05_q90_n10/fs_annots.json

MiewID pickle:
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/<DATASET>/many_t05_q90_n10/miewid_embeddings.pickle
```

The provenance files beside this pair are:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/<DATASET>/many_t05_q90_n10/frame_sampling_config.yaml
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/<DATASET>/many_t05_q90_n10/operating_point_metadata.yaml
```

### Thresholds 0.40 through 0.95

For each `<DATASET>` and each `<LABEL>` in
`40,45,50,55,60,65,70,75,80,85,90,95`, use this pair:

```text
Threshold root:
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/<DATASET>_test_mavric_imageomics/<DATASET>_IA_<LABEL>

Annotation JSON:
<THRESHOLD_ROOT>/frame_sampling/fs_annots.json

MiewID pickle:
<THRESHOLD_ROOT>/miew_id/miewid_embeddings.pickle
```

The provenance files for each of these runs are:

```text
<THRESHOLD_ROOT>/frame_sampling/frame_sampling_config.yaml
<THRESHOLD_ROOT>/metadata.yaml
```

For example, the clean inputs for session 7 at 0.75 are:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/Plains_Experiment_7_test_mavric_imageomics/Plains_Experiment_7_IA_75/frame_sampling/fs_annots.json

/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/Plains_Experiment_7_test_mavric_imageomics/Plains_Experiment_7_IA_75/miew_id/miewid_embeddings.pickle
```

### Optional machine-readable path indexes

The same paths are indexed in two tab-separated manifests:

```text
0.35:
/users/PAS2136/upadha2/mavric-video-pipeline/ablation/ra_selection/generated/operating_point_manifest.tsv

0.40--0.95:
/users/PAS2136/upadha2/mavric-video-pipeline/ablation/ia_threshold/generated/pre_lca_manifest.tsv
```

In either manifest, the only handoff columns needed here are `fs_json` and
`embedding_pickle`. **Do not use the `lca_dir` column as the destination for
the new run.** It is a historical generic path and does not identify a fresh
rerun output.

## 4. Input contract

Each MiewID pickle is a two-element tuple:

1. an `N x 2152` embedding array;
2. an ordered list of `N` annotation UUIDs.

For every run, the UUID list is in exactly the same order as the annotations
in `fs_annots.json`. Downstream code must preserve this alignment. Do not sort,
filter, or reorder one file without making the identical change to the other.

The following validation has already been completed over all 169 input pairs:

- all annotation JSONs, embedding pickles, and metadata files exist;
- annotation count = embedding-row count = UUID-list count for every run;
- JSON annotation UUID order exactly equals pickle UUID order;
- every embedding has dimension 2,152;
- no selected annotation has a negative integer `tracking_id`;
- 17,096 total embedding rows were checked;
- **zero validation problems were found**.

## 5. Expected selected-RA counts

Use this table as the first downstream sanity check. Each cell is
`left RAs/right RAs`, computed directly from the clean JSON file.

| Dataset | 0.35 | 0.40 | 0.45 | 0.50 | 0.55 | 0.60 | 0.65 | 0.70 | 0.75 | 0.80 | 0.85 | 0.90 | 0.95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Grevys_Experiment_1 | 39/26 | 39/26 | 39/26 | 38/26 | 37/25 | 37/24 | 34/24 | 31/22 | 29/21 | 23/20 | 18/17 | 10/10 | 3/6 |
| Grevys_Experiment_2 | 24/4 | 24/3 | 24/1 | 24/1 | 24/1 | 24/1 | 22/1 | 22/1 | 19/1 | 19/1 | 15/1 | 5/0 | 1/0 |
| Grevys_Experiment_3 | 58/64 | 54/63 | 53/62 | 51/60 | 49/59 | 47/59 | 44/58 | 41/53 | 41/52 | 37/49 | 34/43 | 22/32 | 14/16 |
| Grevys_Experiment_4 | 34/22 | 34/22 | 34/22 | 34/22 | 34/21 | 33/20 | 31/18 | 26/15 | 21/13 | 18/10 | 13/9 | 3/4 | 0/3 |
| Grevys_Experiment_5 | 16/73 | 16/73 | 14/71 | 12/71 | 12/70 | 12/70 | 9/69 | 9/67 | 9/66 | 8/62 | 5/53 | 5/40 | 2/13 |
| Grevys_Experiment_6 | 33/122 | 33/122 | 33/122 | 32/122 | 32/120 | 32/119 | 31/119 | 30/114 | 30/111 | 29/107 | 27/97 | 20/69 | 10/36 |
| Plains_Experiment_7 | 90/36 | 85/32 | 79/31 | 79/29 | 77/27 | 73/25 | 70/24 | 67/22 | 66/20 | 65/16 | 59/14 | 47/10 | 20/6 |
| Plains_Experiment_8 | 53/13 | 51/10 | 50/10 | 49/7 | 49/5 | 46/5 | 42/3 | 39/1 | 37/0 | 32/0 | 29/0 | 23/0 | 12/0 |
| Plains_Experiment_9 | 181/9 | 181/9 | 180/8 | 180/8 | 179/8 | 179/8 | 178/8 | 178/8 | 178/5 | 172/5 | 169/3 | 153/3 | 123/0 |
| Plains_Experiment_10 | 48/98 | 48/97 | 47/97 | 47/96 | 47/96 | 47/93 | 46/94 | 46/92 | 46/92 | 46/92 | 45/88 | 37/73 | 17/43 |
| Plains_Experiment_11 | 83/113 | 82/111 | 82/111 | 82/110 | 82/105 | 82/103 | 82/102 | 82/100 | 82/99 | 79/94 | 75/88 | 72/78 | 56/42 |
| Giraffe_Experiment_12 | 123/134 | 122/129 | 119/126 | 118/117 | 115/113 | 110/108 | 105/103 | 101/101 | 94/94 | 82/83 | 61/64 | 28/48 | 11/11 |
| Giraffe_Experiment_13 | 53/79 | 53/78 | 54/76 | 52/75 | 49/73 | 47/71 | 45/69 | 44/67 | 39/64 | 33/59 | 27/45 | 17/25 | 5/11 |
| **Total** | **835/793** | **822/775** | **808/763** | **798/744** | **786/723** | **769/706** | **739/692** | **716/663** | **691/638** | **643/598** | **577/522** | **442/392** | **274/187** |

The aggregate totals and the deterministic exhaustive same-view baselines are:

| `theta_A` | Left RAs | Right RAs | Total RAs | Exhaustive same-view RA pairs |
|---:|---:|---:|---:|---:|
| 0.35 | 835 | 793 | 1,628 | 75,368 |
| 0.40 | 822 | 775 | 1,597 | 73,118 |
| 0.45 | 808 | 763 | 1,571 | 71,182 |
| 0.50 | 798 | 744 | 1,542 | 69,138 |
| 0.55 | 786 | 723 | 1,509 | 66,548 |
| 0.60 | 769 | 706 | 1,475 | 63,930 |
| 0.65 | 739 | 692 | 1,431 | 61,416 |
| 0.70 | 716 | 663 | 1,379 | 58,391 |
| 0.75 | 691 | 638 | 1,329 | 55,598 |
| 0.80 | 643 | 598 | 1,241 | 49,698 |
| 0.85 | 577 | 522 | 1,099 | 41,382 |
| 0.90 | 442 | 392 | 834 | 27,967 |
| 0.95 | 274 | 187 | 461 | 12,375 |

For each threshold, the exhaustive count is computed **within each session**
and then summed:

```text
sum over sessions s of [C(M_s,left, 2) + C(M_s,right, 2)]
```

It is not computed by pooling all left RAs or all right RAs across sessions.

## 6. Why the downstream rerun is required

The tracker uses `-1` as a sentinel for a detection that was not assigned to a
valid track. Four such pseudo-track RAs had entered some historical
per-session selected inputs. They have now been removed from the selected JSON
and the corresponding aligned row has been removed from each MiewID pickle.

| Dataset | Viewpoint | Removed UUID | IA score | Affected thresholds |
|---|---|---|---:|---|
| `Grevys_Experiment_1` | right | `22803907-9854-48c9-9fbc-7fa9e80cca12` | 0.613926 | 0.35--0.60 |
| `Plains_Experiment_7` | left | `a29d8772-e8ad-46dc-9498-5ae64bf594a4` | 0.968772 | 0.35--0.95 |
| `Plains_Experiment_9` | left | `811bf342-5b56-4589-b8aa-40d1f7164aed` | 0.902614 | 0.35--0.90 |
| `Plains_Experiment_11` | left | `d24ca495-2c2d-41bf-a129-18cf715170da` | 0.978756 | 0.35--0.95 |

There were 44 affected session-threshold input pairs, but the decision is to
rerun **all 169** per-session cases so that every point in the threshold sweep
comes from one uniform downstream execution.

At the selected threshold 0.75, the corrected cases are:

| Session | Historical left/right RAs | Clean left/right RAs |
|---|---:|---:|
| Session 7 | 67/20 | 66/20 |
| Session 9 | 179/5 | 178/5 |
| Session 11 | 83/99 | 82/99 |

The 0.75 exhaustive baseline therefore changes from the historical 55,924 to
**55,598** same-view RA-pair comparisons. Downstream human-review counts and
accuracy metrics cannot be corrected arithmetically; they must come from the
new runs.

## 7. Fresh-output rule

Do not allow an existence check to reuse or skip a historical downstream
result.

- The 13 threshold-0.35 roots have no downstream `lca*` directories and are
  fresh cases.
- Every 0.40--0.95 root has historical `lca_stability_universal_gthuman*`
  directories that predate this cleanup.
- Use a new, clearly dated downstream output namespace for the reruns, or
  explicitly overwrite only after the coauthor has intentionally chosen to
  do so.
- Do not delete the historical outputs during the first rerun pass; keeping
  them permits comparison and recovery.
- The `lca` section in `metadata.yaml` and the `lca_dir` manifest column are
  historical planning metadata, not an instruction to reuse that path.

## 8. Cross-session experiments must remain unchanged

Do not rebuild or rerun any directory beginning with:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/Cross_experiment_identification_
```

This includes the existing 0.35 and 0.75 pooled many-RA experiments. Their
builders had already excluded negative tracking sentinels, their JSON/pickle
pairs remain aligned, and the user has explicitly kept them out of this rerun.

## 9. Downstream completion checklist

For each of the 169 runs, the coauthor should:

1. select the annotation JSON and MiewID pickle using Section 3;
2. confirm the left/right counts against Section 5;
3. write all downstream outputs to a fresh run-specific directory;
4. run Beta Stability using the coauthor's established manuscript procedure;
5. run Tracking-Based Identity Resolution using the same experimental
   response policy as the manuscript;
6. recompute track-level and individual-ID metrics against the fixed ground
   truth, keeping inactive identifiable tracks and IDs as false negatives;
7. record Beta Stability reviews, Tracking-Based Identity Resolution reviews,
   and their sum;
8. count every requested comparison, including a repeated or consistency
   recheck, each time it is requested;
9. regenerate all threshold-sweep summaries and plots from the complete set of
   169 new results;
10. regenerate the per-session 0.75 table and the appendix effort tables;
11. replace the old 55,924 exhaustive count with the clean deterministic count
    55,598 wherever the within-session 0.75 result is reported;
12. do not manually carry forward any historical accuracy or human-review
    value unless it is reproduced by the new run.

A useful completion record has one row per run with these fields:

```text
dataset
threshold
input_annotation_json
input_embedding_pickle
downstream_output_directory
selected_left_RAs
selected_right_RAs
retained_identifiable_tracks
GT_IDs_with_active_tracks
predicted_IDs
beta_stability_reviews
tracking_resolution_reviews
total_reviews
track_TP
track_FP
track_FN
track_precision
track_recall
individual_ID_TP
individual_ID_FP
individual_ID_FN
individual_ID_precision
individual_ID_recall
status
notes
```

The rerun is complete only when all 169 rows are present, all input counts
match this document, and every paper table/plot derived from the within-session
threshold sweep has been regenerated from those rows.

## 10. Audit trail and recovery

The exact cleanup audit, including every affected path and before/after count,
is stored at:

```text
/users/PAS2136/upadha2/mavric-video-pipeline/ablation/ia_threshold/generated/negative_tracking_id_cleanup.tsv
```

The reusable cleanup/validation utility is:

```text
/users/PAS2136/upadha2/mavric-video-pipeline/ablation/ia_threshold/remove_negative_tracking_sentinels.py
```

Original pre-cleanup files and manifests are preserved under:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/negative_tracking_id_cleanup_backup_20260825/
```

The RA-selection implementation was also changed to reject negative numeric
tracking sentinels in future one-RA and many-RA selections:

```text
/users/PAS2136/upadha2/mavric-video-pipeline/VAREID/algo/frame_sampling/frame_sampling.py
```

Tests run after the change:

```text
python -m unittest tests.test_frame_sampling tests.test_ia_threshold_sweep
# 15 passed

python -m unittest discover -s tests -p 'test_cross_experiment*.py'
# 8 passed
```

## 11. Final handoff status

- [x] 13 threshold-0.35 many-RA inputs prepared through MiewID.
- [x] 156 threshold-0.40--0.95 many-RA inputs prepared through MiewID.
- [x] Invalid negative tracking sentinels removed from per-session inputs.
- [x] JSON/pickle ordering and dimensions validated for all 169 pairs.
- [x] Expected left/right RA counts documented.
- [x] Corrected exhaustive baselines documented.
- [x] Cross-session inputs verified as unchanged and excluded.
- [ ] Coauthor runs all 169 downstream experiments.
- [ ] Coauthor aggregates reviews and accuracy metrics.
- [ ] Coauthor regenerates within-session plots and tables.
- [ ] Manuscript numerical claims are updated from the new outputs.
