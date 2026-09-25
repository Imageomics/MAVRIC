#!/bin/bash
#SBATCH --job-name=ra_all_eval
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --account=PAS2136
#SBATCH --output=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_all_eval_%j.out
#SBATCH --error=/fs/scratch/PAS2136/upadha2/mavric-video-pipeline/logs/ra_all_eval_%j.err

set -euo pipefail

REPO=/users/PAS2136/upadha2/mavric-video-pipeline
PYTHON=/users/PAS2136/upadha2/miniconda3/envs/vareid/bin/python

cd "$REPO"
"$PYTHON" -u ablation/ra_selection/evaluate_sweep.py
