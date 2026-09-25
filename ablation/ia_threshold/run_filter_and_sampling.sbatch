#!/bin/bash
#SBATCH --job-name=ia_threshold_fs
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --account=PAS2136
#SBATCH --array=0-155%30
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ia_threshold_fs_%A_%a.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ia_threshold_fs_%A_%a.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
MANIFEST="$REPO/ablation/ia_threshold/generated/manifest.tsv"
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python

cd "$REPO"

ROW_NUMBER=$((SLURM_ARRAY_TASK_ID + 2))
ROW=$(sed -n "${ROW_NUMBER}p" "$MANIFEST")
if [[ -z "$ROW" ]]; then
    echo "No manifest row for Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

IFS=$'\t' read -r TASK_ID DATASET THRESHOLD_LABEL THRESHOLD SOURCE_JSON OUTPUT_DIR FILTERED_JSON SAMPLING_CONFIG CONFIG_SNAPSHOT FS_JSON FILTER_LOG FS_LOG <<< "$ROW"
if [[ "$TASK_ID" != "$SLURM_ARRAY_TASK_ID" ]]; then
    echo "Manifest task $TASK_ID does not match Slurm task $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

mkdir -p "$(dirname "$FILTERED_JSON")" "$(dirname "$FS_JSON")" "$(dirname "$FILTER_LOG")"

if [[ -s "$FS_JSON" ]]; then
    if [[ ! -s "$FILTERED_JSON" ]]; then
        echo "Existing frame-sampling output has no filtered IA input: $FS_JSON" >&2
        exit 1
    fi
    if [[ ! -s "$CONFIG_SNAPSHOT" ]] || ! cmp -s "$SAMPLING_CONFIG" "$CONFIG_SNAPSHOT"; then
        echo "Existing frame-sampling output has a missing or stale config snapshot: $FS_JSON" >&2
        exit 1
    fi
    echo "Validated existing output; skipping $DATASET/IA_$THRESHOLD_LABEL"
    exit 0
fi

cp "$SAMPLING_CONFIG" "$CONFIG_SNAPSHOT"

if [[ ! -s "$FILTERED_JSON" ]]; then
    "$PYTHON" -u ablation/ia_threshold/filter_ia.py \
        "$SOURCE_JSON" \
        "$FILTERED_JSON" \
        "$THRESHOLD" \
        > "$FILTER_LOG" 2>&1
fi

"$PYTHON" -u -m VAREID.algo.frame_sampling.frame_sampling \
    "$FILTERED_JSON" \
    "$FS_JSON" \
    --sampling-config "$CONFIG_SNAPSHOT" \
    > "$FS_LOG" 2>&1

echo "Completed $DATASET at IA threshold $THRESHOLD"
