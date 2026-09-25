# Representative-Annotation Selection Ablation

This sweep evaluates the updated frame-sampling algorithm on all 13 canonical
15 fps experiments. The two 30 fps diagnostic runs and the legacy duplicate
`Grevys_Experiment_6` output are intentionally excluded.

Completed run results and the primary fixed-query comparison are documented in
[`RESULTS.md`](RESULTS.md).

The agreed interpretation and reusable paper language are in
[`PAPER_WRITEUP_NOTES.md`](PAPER_WRITEUP_NOTES.md).

The comparison between manual identity ground truth and session-level animal
counts is documented in
[`SESSION_INDIVIDUAL_COUNT_AUDIT.md`](SESSION_INDIVIDUAL_COUNT_AUDIT.md).

The selected production operating point is `t=5`, `q=0.9`, `n=10`. Its frame
selections and union embeddings already exist for all 13 experiments. Prepare
the configuration-specific embedding pickle, config snapshot, and metadata for
every experiment before LCA with:

```bash
sbatch -A PAS2136 ablation/ra_selection/run_prepare_operating_point.sbatch
```

The resulting pre-LCA contract is:

```text
RA_selection_ablation_15fps/<dataset>/many_t05_q90_n10/
  frame_sampling_config.yaml
  fs_annots.json
  frame_sampling.log
  miewid_embeddings.pickle
  operating_point_metadata.yaml
```

LCA is intentionally not part of the preparation job. When it is time to run
LCA, submit species ranges from `run_operating_point_lca.sbatch`:

```bash
# Grevy's zebra (tasks 0-5)
sbatch -A PAS2136 --array=0-5%6 ablation/ra_selection/run_operating_point_lca.sbatch

# Plains zebra (tasks 6-10)
sbatch -A PAS2136 --array=6-10%5 ablation/ra_selection/run_operating_point_lca.sbatch

# Giraffe (tasks 11-12)
sbatch -A PAS2136 --array=11-12%2 ablation/ra_selection/run_operating_point_lca.sbatch
```

Outputs are stored under
`RA_selection_ablation_15fps/<dataset>/many_t05_q90_n10/lca_stability_universal/`.

The sweep contains one `selection_mode: one` baseline and 27 `many`-mode cells:

- `t_seconds`: 5, 10, 15
- `quality_threshold_pct`: 0.7, 0.8, 0.9
- `num_RA_annots`: 3, 5, 10
- `frame_interval`: fixed at 15

Generate one immutable YAML per dataset/configuration and the 364-row task
manifest:

```bash
cd /users/PAS2136/upadha2/mavric-video-pipeline
python ablation/ra_selection/generate_sweep.py
```

Submit the CPU-only frame-sampling array:

```bash
sbatch -A PAS2136 /users/PAS2136/upadha2/mavric-video-pipeline/ablation/ra_selection/run_frame_sampling_ablation.sbatch
```

Completed outputs are skipped, so the same array can safely be resubmitted.
Outputs are written below:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/RA_selection_ablation_15fps/<dataset>/<run>/fs_annots.json
```

After the array finishes, summarize annotation counts and detect parameter cells
that selected exactly the same annotation UUIDs:

```bash
python ablation/ra_selection/summarize_selections.py
```

Build one MiewID input containing the union of selected annotations for each of
the 13 experiments, then submit the GPU array:

```bash
python ablation/ra_selection/build_embedding_unions.py
sbatch -A PAS2136 /users/PAS2136/upadha2/mavric-video-pipeline/ablation/ra_selection/run_union_embeddings.sbatch
```

Each union JSON, embedding pickle, and detailed inference log is stored under
`RA_selection_ablation_15fps/<dataset>/embedding_union/`. The original experiment
folders are read-only inputs and are never modified by this ablation.

After all 13 embedding tasks complete, evaluate every configuration from the
cached union embeddings:

```bash
python ablation/ra_selection/evaluate_sweep.py
```

For a scheduled embedding array, the evaluation can instead be submitted with
an `afterok` dependency so it starts only when every embedding task succeeds.

The evaluator writes per-experiment, per-species, and all-dataset aggregate CSV
files to the ablation output root's `evaluation/` directory. `paper_map5` allows
same-TID positives for comparison with the earlier analysis; `strict_map5`
restricts the gallery to the same viewpoint, removes the query TID, and uses
standard AP@5. `fixed_map5` is the primary comparison: it uses the same one-best
GT query set for every configuration and excludes the query TID from each
configuration-specific gallery.

Embedding and retrieval evaluation should consume only unique selection hashes.
For the strict result, exclude same-TID gallery items and evaluate a fixed query
set whose ground-truth identities have a positive in another track. Also report
the paper-style self-only exclusion metric for comparison and average selected
annotation count for each parameter cell.
