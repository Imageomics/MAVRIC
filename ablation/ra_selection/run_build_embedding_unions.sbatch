#!/bin/bash
#SBATCH --job-name=ra_build_unions
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --account=PAS2136
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_build_unions_%j.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_build_unions_%j.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python

cd "$REPO"
"$PYTHON" -u ablation/ra_selection/summarize_selections.py
"$PYTHON" -u ablation/ra_selection/build_embedding_unions.py
