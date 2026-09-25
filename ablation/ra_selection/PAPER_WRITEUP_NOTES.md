# Paper Write-Up Notes: RA-Selection Ablation

## Status

These notes capture the agreed interpretation of the completed 13-experiment,
15 fps representative-annotation (RA) selection ablation. Use this document when
rewriting the paper and supplementary material. Raw run details are in
[`RESULTS.md`](RESULTS.md).

## Experimental Protocol

- Tuning set: Grevy's zebra Experiments 1-3.
- Held-out groups: Grevy's zebra Experiments 4-6, Plains zebra Experiments
  7-11, and giraffe Experiments 12-13.
- The held-out score is a macro-average of those three group means, giving each
  species/session group equal weight.
- Sweep: `t_seconds` in `{5, 10, 15}`, `quality_threshold_pct` in
  `{0.7, 0.8, 0.9}`, and `num_RA_annots` in `{3, 5, 10}`.
- Baseline: one best annotation per track and viewpoint.
- `frame_interval` is fixed at 15 for all experiments.

## Primary Metric

Use `fixed_map5` as the primary parameter-selection metric.

The fixed query set consists of one-best GT annotations whose identity has at
least one other tracking ID in the same viewpoint. Every configuration is
evaluated with the same queries. Gallery annotations come from the configuration
being evaluated, are restricted to the query viewpoint, and cannot share the
query tracking ID.

- Fixed queries across all 13 experiments: 553 for every configuration.
- Fixed held-out queries: 467 for every configuration.

`strict_map5` excludes same-TID gallery matches, but uses every selected RA as a
query. Its all-dataset query count ranges from 553 to 1,850, while its held-out
query count ranges from 467 to 1,587. It therefore changes the weighting of
tracks and identities across configurations. Report it only as a secondary
diagnostic, not as the basis for selecting parameters.

## Table B16-Style Summary

| Objective | t (s) | Quality | RA cap | Tune annots. | Tune fixed mAP@5 | Held-out annots. | Held-out fixed mAP@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Highest held-out fixed mAP | 5 | 0.8 | 10 | 87.3 | 0.87897 | 175.4 | **0.79329** |
| Balanced operating point | 5 | 0.9 | 10 | 72.0 | 0.87581 | 146.6 | **0.78411** |
| Lower-budget alternative | 5 | 0.9 | 5 | 70.7 | 0.86841 | 126.3 | 0.77622 |
| Low-budget multi-RA | 5 | 0.9 | 3 | 61.7 | 0.84276 | 108.3 | 0.77235 |
| One-best baseline | - | - | 1 | 38.0 | 0.84706 | 67.1 | 0.75190 |

The selected operating point is:

```text
t_seconds = 5
quality_threshold_pct = 0.9
num_RA_annots = 10
```

This is an annotation-budget choice, not the unique empirical optimum. Relative
to `t=5, q=0.8, n=10`, it reduces held-out annotations from 175.4 to 146.6
(16.4%) while reducing fixed mAP@5 from 0.79329 to 0.78411 (0.92 percentage
points).

## Main Findings

### Temporal spacing is the clearest signal

The most robust result is `t_seconds=5`. It consistently occupies the strongest
part of the aggregate rankings and replicates the original paper's preference
for a five-second temporal threshold. Do not claim that it wins literally every
individual ranking.

### There is no sharp mid-budget optimum

Several configurations have nearly identical annotation costs and fixed mAP:

| Configuration | Held-out annots. | Held-out fixed mAP@5 |
| --- | ---: | ---: |
| `t5_q80_n05` | 146.0 | 0.78264 |
| `t5_q90_n10` | 146.6 | 0.78411 |
| `t5_q70_n05` | 157.2 | 0.78449 |

The quality gate trades annotation count for mAP smoothly. Present `q=0.9,
n=10` as a reproducible balanced choice, not as a distinguished knee in the
curve.

### Multi-RA improves fixed mAP

On the held-out macro-average, the balanced multi-RA configuration improves
fixed mAP@5 from 0.75190 for one-best to 0.78411, an increase of 3.22 percentage
points. On Plains zebra, it improves fixed mAP@5 from 0.59143 to 0.65863, an
increase of 6.72 percentage points.

Fixed Hit@5 declines from 0.96783 to 0.94814 as the held-out gallery grows from
67.1 to 146.6 annotations on average. Report this descriptively. The experiment
does not isolate whether the change comes from gallery size, sampling behavior,
or another mechanism.

### The RA cap rarely binds

For `t=5, q=0.9, n=10`, only 26 of 716 track-viewpoint groups (3.6%) reach the
ten-annotation cap, and 89.5% select five or fewer RAs. Temporal suppression and
the quality gate therefore control most selections; changing the cap has a
smaller effect.

### Plains zebra is the lowest-performing group

At the balanced operating point, held-out fixed mAP@5 is 0.79346 for Grevy's
zebra Experiments 4-6, 0.65863 for Plains zebra, and 0.90023 for giraffe. State
that Plains is the lowest-performing group, but do not assign the cause. Possible
contributors include embedding domain fit, viewpoint errors, crop quality,
animal scale, occlusion, tracking fragmentation, and ground-truth difficulty;
none has been isolated by this ablation.

## Paper-Ready Wording

### Methods

> We selected representative-annotation parameters using a fixed-query
> retrieval protocol. One ground-truth representative per eligible track and
> viewpoint formed a query set that remained identical across all parameter
> configurations. For each configuration, its selected annotations formed the
> gallery; gallery samples were restricted to the query viewpoint, and samples
> sharing the query tracking ID were excluded. We report mAP@5 over 467 fixed
> held-out queries, macro-averaged across Grevy's zebra Experiments 4-6, Plains
> zebra Experiments 7-11, and giraffe Experiments 12-13.

### Results and operating point

> A five-second temporal spacing produced the strongest results across the
> parameter sweep. The highest held-out fixed mAP@5 was obtained with
> `t=5`, `q=0.8`, and `n=10` (0.7933; 175.4 annotations on average). We selected
> `t=5`, `q=0.9`, and `n=10` as the operating point because it reduced the
> annotation count by 16.4% (146.6 annotations) for a 0.92 percentage-point
> reduction in fixed mAP@5 (0.7841). Nearby mid-budget configurations performed
> similarly, indicating a smooth annotation-performance trade-off rather than a
> sharply defined optimum.

### Multi-RA comparison

> The selected multi-RA configuration improved held-out fixed mAP@5 from 0.7519
> for the one-best baseline to 0.7841. Hit@5 decreased slightly as the gallery
> size increased; because gallery size and sampling configuration change
> together, we report this observation without attributing a causal mechanism.

## Claims to Avoid

- Do not claim that `q=0.9, n=10` is the highest-scoring fixed-query setting.
- Do not use `strict_map5` to rank configurations because its query population
  changes with the number and distribution of selected RAs.
- Do not claim a tuning-to-held-out inversion or overfitting. That pattern was an
  artifact of the changing strict-query population and disappears under
  fixed-query evaluation.
- Do not claim that the original Table B16 maximum-mAP row would have been the
  wrong operating point based on this ablation.
- Do not describe the Hit@5 decrease as a demonstrated coverage or ranking
  mechanism; gallery size is confounded.
- Do not attribute Plains zebra performance solely to the re-identification
  embedding without a controlled error analysis.
- Do not describe `q=0.9, n=10` as a natural knee or uniquely distinguished
  Pareto point.

## Source Tables

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/all_per_experiment.csv
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/species_aggregate.csv
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/all_aggregate.csv
```
