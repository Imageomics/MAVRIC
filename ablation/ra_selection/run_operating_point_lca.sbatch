#!/bin/bash
#SBATCH --job-name=ra_op_lca
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --account=PAS2136
#SBATCH --array=0-12%6
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_op_lca_%A_%a.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_op_lca_%A_%a.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python
MANIFEST="$REPO/ablation/ra_selection/generated/operating_point_manifest.tsv"

export PATH="/users/PAS2136/upadha2/miniconda3/envs/vareid/bin:$PATH"

cd "$REPO"

ROW_NUMBER=$((SLURM_ARRAY_TASK_ID + 2))
ROW=$(sed -n "${ROW_NUMBER}p" "$MANIFEST")
if [[ -z "$ROW" ]]; then
    echo "No embedding manifest row for Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

IFS=$'\t' read -r TASK_ID DATASET SPECIES RUN_NAME SOURCE_IA SAMPLING_CONFIG SELECTED_JSON NUM_ANNOTATIONS SELECTED_PICKLE METADATA_YAML LCA_DIR LEFT_OUTPUT RIGHT_OUTPUT PRE_LCA_STATUS LCA_STATUS <<< "$ROW"
if [[ "$TASK_ID" != "$SLURM_ARRAY_TASK_ID" ]]; then
    echo "Manifest task $TASK_ID does not match Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

if [[ -s "$LEFT_OUTPUT" && -s "$RIGHT_OUTPUT" ]]; then
    echo "LCA outputs already exist; skipping $DATASET"
    exit 0
fi

if [[ ! -s "$SELECTED_JSON" ]]; then
    echo "Missing operating-point selection: $SELECTED_JSON" >&2
    exit 1
fi
if [[ ! -s "$SELECTED_PICKLE" ]]; then
    echo "Missing selected embedding cache: $SELECTED_PICKLE" >&2
    exit 1
fi
if [[ "$PRE_LCA_STATUS" != "ready" ]]; then
    echo "Dataset is not marked ready before LCA: $DATASET ($PRE_LCA_STATUS)" >&2
    exit 1
fi

"$PYTHON" -u -m VAREID.algo.lca.lca \
    "$SELECTED_JSON" \
    "$SELECTED_PICKLE" \
    "$LCA_DIR" \
    lca \
    annots \
    "$LCA_DIR/lca_algorithm.txt" \
    "$LCA_DIR/lca.txt" \
    --video \
    --separate_viewpoints
