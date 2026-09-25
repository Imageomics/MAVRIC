# Cross-Experiment Identification Bundles

This workflow combines the canonical IA35, one-best frame-sampling outputs into
one pre-LCA bundle per species group:

- Grevy's zebra: Experiments 1-6
- Plains zebra: Experiments 7-11
- Giraffe: Experiments 12-13

The source `frame_sampling_IA35/fs_annots.json` files were validated against the
RA-selection ablation's `one_best` files. They are byte-identical, contain
exactly one annotation per `(viewpoint, tracking_id)` group, and align exactly
with their `miew_id_IA_35/miewid_embeddings.pickle` UUID order.

## Tracking-ID Remapping

Tracker IDs are session-local and can repeat in different experiments. Each
species bundle therefore assigns contiguous global tracking IDs using the key:

```text
(source_experiment, original_tracking_id) -> global_tracking_id
```

The same original TID in the left and right viewpoints of one experiment keeps
one global TID. The same numeric TID in two different experiments receives two
different global TIDs.

Every combined annotation retains:

- `tracking_id`: global species-bundle TID used by LCA
- `original_tracking_id`: original session-local TID
- `source_experiment`: experiment name
- `source_tracking_key`: readable `<experiment>:<original_tid>` key

The mapping is also written in TSV and JSON forms. Negative tracker sentinel
IDs (`-1`) are excluded, along with their corresponding embedding rows, and are
listed under `excluded_annotations` in `tracking_id_map.json`.

## Outputs

Outputs are stored under:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  Cross_experiment_identification_IA35/
```

Each of `grevys/`, `plains/`, and `giraffes/` contains:

```text
combined_one_best_fs_annots.json
combined_one_best_miewid_embeddings.pickle
tracking_id_map.tsv
tracking_id_map.json
source_manifest.tsv
metadata.yaml
```

`source_manifest.tsv` records source paths, counts, and SHA-256 checksums. The
root `bundle_manifest.tsv` inventories all three bundles.

LCA is intentionally not run by the bundle builder. When LCA is run, viewpoints
must remain separate so bilaterally asymmetric left/right appearances are not
clustered directly together.

## Ground-Truth Representative Bundles

For reduced cross-session manual review, a second output family uses only TIDs
assigned to manually established ground-truth identities. It selects the
highest-CA one-best annotation across all assigned TIDs independently for each
available identity/viewpoint.

```bash
python -m ablation.cross_experiment.build_gt_representative_bundles
```

These reduced bundles are stored under:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  Cross_experiment_identification_IA35_GT_representatives/
```

Each species directory contains the combined annotation/embedding files plus
`identity_map.tsv`, `identity_map.json`, and `representative_selection.tsv`.
The global `tracking_id` represents a unique `(experiment, ground-truth ID)`;
left and right representatives for that identity share it even when different
original TIDs were selected. Non-ID TIDs never enter these bundles.

Manually established cross-session identity ground truth is stored separately
from the generated bundles:

```text
ablation/cross_experiment/grevys_cross_session_ground_truth.yaml
ablation/cross_experiment/plains_cross_session_ground_truth.yaml
ablation/cross_experiment/giraffes_cross_session_ground_truth.yaml
```

Its TIDs use the reduced bundle's `tracking_id` namespace. A bundle TID listed
under both viewpoints is a known within-session left-right link. Multiple TIDs
in one viewpoint list would represent a manually accepted cross-session match.

## Build

From the repository root:

```bash
python -m ablation.cross_experiment.build_bundles
```

## IA75 Many-Mode Pipeline Bundles

The selected operating point (`many_t05_q90_n10`) is combined across sessions
with:

```bash
python -m ablation.cross_experiment.build_bundles \
  --config ablation/cross_experiment/datasets_ia75_many.yaml
```

Outputs are written to:

```text
/fs/ess/PAS2136/ggr_data/results/IJCV_MAVRIC_Ground_Truth/
  Cross_experiment_identification_IA75_many/
```

The IA75 bundle keeps every selected RA. Its `tracking_id` values remain
tracker-fragment IDs, using the stable IA35 registry keyed by
`(source_experiment, original_tracking_id)`. This prevents session-local TID
collisions without injecting identity ground truth into LCA.

Each species directory also contains `ground_truth_projection.yaml` and
`ground_truth_track_map.tsv`. These evaluation-only sidecars project the
existing cross-session biological identity IDs into the IA75 global-track
namespace. They are not included in the annotation JSON passed to LCA.

The generated `lca_post_config.yaml` can run the remaining stages:

```bash
python -m VAREID.drivers.lca_driver --config_path \
  /path/to/species/lca_post_config.yaml

python -m VAREID.drivers.post_driver \
  /path/to/species/lca_post_config.yaml
```

LCA remains separated by viewpoint. Postprocessing uses shared global tracker
IDs as cross-view evidence, while final performance is measured against the
ground-truth projection sidecar.

## IA35 Many-Mode Pipeline Bundles

The comparable many-RA inference bundle at the ground-truth candidate
threshold uses the already materialized `many_t05_q90_n10` selections:

```bash
python -m ablation.cross_experiment.build_bundles \
  --config ablation/cross_experiment/datasets_ia35_many.yaml
```

This writes the three pooled species inputs to
`Cross_experiment_identification_IA35_many/`. It is an inference bundle at
`theta_A = 0.35`, not the one-best bundle used to organize ground-truth
curation.
