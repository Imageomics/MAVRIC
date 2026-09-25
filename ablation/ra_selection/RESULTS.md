# RA-Selection Ablation Results

For the agreed interpretation, reporting cautions, and paper-ready language, see
[`PAPER_WRITEUP_NOTES.md`](PAPER_WRITEUP_NOTES.md).

## Scope

- 13 canonical 15 fps experiments: Grevy 1-6, Plains 7-11, Giraffe 12-13
- 28 configurations per experiment: one-best plus the 3 x 3 x 3 many-mode grid
- 364 completed selection outputs
- 2,387 unique selected annotations embedded once through MiewID
- 50 parameter cells collapsed to another cell's identical selected-UUID set

All generated selections, unions, embeddings, and evaluations are isolated under:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps
```

## Primary Metric

`fixed_map5` uses the one-best GT annotations as an identical query set for every
configuration. Gallery annotations come from the configuration being evaluated,
are restricted to the query viewpoint, and cannot share the query tracking ID.
Queries are eligible only when the GT identity has another track in that
viewpoint.

## All-Dataset Results

The table macro-averages over the 13 experiments.

| Configuration | Avg. annotations | Fixed mAP@5 | Fixed hit@5 |
| --- | ---: | ---: | ---: |
| `one_best` | 55.08 | 0.739108 | 0.970402 |
| `t=5, q=0.9, n=5` | 107.00 | 0.766395 | 0.960539 |
| `t=5, q=0.9, n=10` | 125.54 | 0.777033 | 0.954542 |
| `t=5, q=0.8, n=10` | 147.85 | 0.787309 | 0.955895 |
| `t=5, q=0.7, n=10` | 160.77 | 0.789058 | 0.954754 |

The maximum fixed mAP@5 row is `t=5, q=0.7, n=10`. The more conservative
`t=5, q=0.9, n=10` operating point uses about 22% fewer annotations while giving
up approximately 0.012 absolute fixed mAP@5. It remains close to the best row
within each species and is the balanced candidate for the final pipeline.

## Result Tables

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/all_per_experiment.csv
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/species_aggregate.csv
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/evaluation/all_aggregate.csv
```

The historical `paper_map5` and self-query `strict_map5` metrics are retained in
the CSV files for comparison. `fixed_map5` should be used for parameter selection.
