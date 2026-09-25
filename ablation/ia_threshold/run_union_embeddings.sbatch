#!/bin/bash
#SBATCH --job-name=ia_union_miewid
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --account=PAS2136
#SBATCH --partition=quad
#SBATCH --gres=gpu:1
#SBATCH --array=0-12%7
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ia_union_miewid_%A_%a.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ia_union_miewid_%A_%a.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
MANIFEST="$REPO/ablation/ia_threshold/generated/embedding_manifest.tsv"
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

cd "$REPO"

ROW_NUMBER=$((SLURM_ARRAY_TASK_ID + 2))
ROW=$(sed -n "${ROW_NUMBER}p" "$MANIFEST")
if [[ -z "$ROW" ]]; then
    echo "No embedding manifest row for Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

IFS=$'\t' read -r TASK_ID DATASET UNION_JSON MODEL_URL EMBEDDING_PICKLE RUN_LOG NUM_ANNOTATIONS <<< "$ROW"
if [[ "$TASK_ID" != "$SLURM_ARRAY_TASK_ID" ]]; then
    echo "Manifest task $TASK_ID does not match Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

if [[ -s "$EMBEDDING_PICKLE" ]]; then
    if "$PYTHON" -u ablation/ia_threshold/validate_embedding_cache.py "$UNION_JSON" "$EMBEDDING_PICKLE"; then
        echo "Validated existing embedding union; skipping $DATASET"
        exit 0
    fi
    echo "Existing embedding union is stale; regenerating $DATASET"
fi

echo "Embedding $NUM_ANNOTATIONS annotations for $DATASET"
"$PYTHON" -u -m VAREID.algo.miew_id.miew_id \
    "$UNION_JSON" \
    "$MODEL_URL" \
    "$EMBEDDING_PICKLE" \
    > "$RUN_LOG" 2>&1
