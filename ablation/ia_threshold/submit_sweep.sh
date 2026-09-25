#!/bin/bash
set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline

selection_job=$(sbatch -A PAS2136 --parsable "$REPO/ablation/ia_threshold/run_filter_and_sampling.sbatch")
selection_job=${selection_job%%;*}
union_job=$(sbatch -A PAS2136 --parsable --dependency="afterok:$selection_job" "$REPO/ablation/ia_threshold/run_build_embedding_unions.sbatch")
union_job=${union_job%%;*}
embedding_job=$(sbatch -A PAS2136 --parsable --dependency="afterok:$union_job" "$REPO/ablation/ia_threshold/run_union_embeddings.sbatch")
embedding_job=${embedding_job%%;*}
materialize_job=$(sbatch -A PAS2136 --parsable --dependency="afterok:$embedding_job" "$REPO/ablation/ia_threshold/run_materialize_pre_lca.sbatch")
materialize_job=${materialize_job%%;*}

echo "Filter/frame-sampling array: $selection_job"
echo "Build embedding unions:     $union_job"
echo "MiewID embedding array:     $embedding_job"
echo "Materialize pre-LCA files:  $materialize_job"
