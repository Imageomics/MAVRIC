#!/bin/bash
#SBATCH --job-name=ra_selection_15fps
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --account=PAS2136
#SBATCH --array=0-363%30
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_selection_15fps_%A_%a.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_selection_15fps_%A_%a.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
MANIFEST="$REPO/ablation/ra_selection/generated/manifest.tsv"
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python

cd "$REPO"

ROW_NUMBER=$((SLURM_ARRAY_TASK_ID + 2))
ROW=$(sed -n "${ROW_NUMBER}p" "$MANIFEST")
if [[ -z "$ROW" ]]; then
    echo "No manifest row for Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

IFS=$'\t' read -r TASK_ID DATASET RUN_NAME INPUT_JSON SAMPLING_CONFIG OUTPUT_JSON RUN_LOG <<< "$ROW"
if [[ "$TASK_ID" != "$SLURM_ARRAY_TASK_ID" ]]; then
    echo "Manifest task $TASK_ID does not match Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_JSON")"

if [[ -s "$OUTPUT_JSON" ]]; then
    echo "Output already exists; skipping $DATASET/$RUN_NAME"
    exit 0
fi

"$PYTHON" -u -m VAREID.algo.frame_sampling.frame_sampling \
    "$INPUT_JSON" \
    "$OUTPUT_JSON" \
    --sampling-config "$SAMPLING_CONFIG" \
    > "$RUN_LOG" 2>&1
