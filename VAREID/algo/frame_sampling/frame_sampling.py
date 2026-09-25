import random
import argparse
from numbers import Real
import numpy as np
import pandas as pd
from collections import defaultdict
from VAREID.libraries.io.format_funcs import load_config, load_json, save_json, split_dataframe, join_dataframe_dict
from VAREID.libraries.utils import path_from_file

# ============================================================================
# STRATIFICATION LOGIC
# ============================================================================

def get_ca_score(annotation, default=0.0):
    """Return a numeric CA score, including for annotations with a null score."""
    score = annotation.get('CA_score')
    return default if score is None else score

def has_negative_tracking_sentinel(annotation):
    """Return whether an annotation has a negative numeric tracking sentinel."""
    tracking_id = annotation.get('tracking_id')
    return isinstance(tracking_id, Real) and tracking_id < 0

def get_stratified_ras(anns, num_ras):
    """
    Final step: Divide candidates into temporal bins and pick the highest
    CA_score frame from each bin. Ties favor the earlier frame.
    """
    if len(anns) <= num_ras:
        return anns

    anns.sort(key=lambda x: x['frame_number'])
    n = len(anns)
    bins = np.array_split(range(n), num_ras)

    selected = []
    for bin_indices in bins:
        if len(bin_indices) == 0: continue
        segment = [anns[i] for i in bin_indices]
        # Tie-breaker: Highest CA score first; if equal, earliest frame first
        # Sorting (CA, frame) in reverse order means higher CA wins, then lower frame wins
        segment.sort(key=lambda a: (get_ca_score(a), -a['frame_number']), reverse=True)
        selected.append(segment[0])

    return selected

# ============================================================================
# 'MANY' MODE: ROBUST TEMPORAL NMS
# ============================================================================

def run_many_mode_logic(data, cfg):
    t_sec = cfg['thresholds']['t_seconds']
    f_int = cfg['thresholds']['frame_interval']
    t_frames = max(1, int(round(t_sec * f_int)))
    qual_pct = cfg['thresholds'].get('quality_threshold_pct', 0.8)
    num_ras = cfg['settings'].get('num_RA_annots', 5)
    use_vp = cfg['settings'].get('use_viewpoint', True)
    use_ca_master = cfg['settings'].get('use_ca_score', True)

    processed_annots = []
    by_vp_tid = defaultdict(lambda: defaultdict(list))

    for ann in data['annotations']:
        if has_negative_tracking_sentinel(ann):
            continue
        vp = ann.get('viewpoint', 'unknown') if use_vp else 'unknown'
        by_vp_tid[vp][ann['tracking_id']].append(ann)

    for vp, tracks in by_vp_tid.items():
        for tid, anns in tracks.items():
            anns.sort(key=lambda x: x['frame_number'])

            # 1. Quality baseline and guaranteed representative per track
            use_ca_for_track = use_ca_master
            if use_ca_master:
                ca_vals = [a.get('CA_score') for a in anns if a.get('CA_score') is not None]
                if not ca_vals:
                    use_ca_for_track = False
                else:
                    global_max = max(ca_vals)
                    qual_thresh = global_max * qual_pct
                    global_best = max(
                        (a for a in anns if a.get('CA_score') is not None),
                        key=lambda a: (get_ca_score(a), -a['frame_number']),
                    )

            if not use_ca_for_track:
                global_max, qual_thresh = 1.0, -float('inf')
                global_best = min(anns, key=lambda a: a['frame_number'])

            # 2. Candidate Selection. The global best is always eligible, even
            # when it is an endpoint or no interior peak passes the quality gate.
            candidates = [global_best]
            for i, cur in enumerate(anns):
                if cur is global_best:
                    continue

                score = get_ca_score(cur, -float('inf')) if use_ca_for_track else 1.0
                if score < qual_thresh: continue

                # Check neighbors for interior peak status
                if 0 < i < len(anns) - 1:
                    prev_s = get_ca_score(anns[i-1], -float('inf')) if use_ca_for_track else 1.0
                    next_s = get_ca_score(anns[i+1], -float('inf')) if use_ca_for_track else 1.0
                    if score >= prev_s and score >= next_s:
                        candidates.append(cur)
                elif len(anns) <= 2:
                    candidates.append(cur)

            # 3. TRUE NMS-IN-TIME (Deterministic Greedy Selection)
            # Higher CA score preferred; earlier frame number preferred for ties
            candidates.sort(key=lambda a: (get_ca_score(a), -a['frame_number']), reverse=True)

            selected_nms, selected_frames = [], []
            for cand in candidates:
                fn = cand['frame_number']
                if all(abs(fn - sfn) >= t_frames for sfn in selected_frames):
                    selected_nms.append(cand)
                    selected_frames.append(fn)

            # 4. Final Stratification (Temporal Coverage)
            spaced_candidates = sorted(selected_nms, key=lambda a: a['frame_number'])
            final_ras = get_stratified_ras(spaced_candidates, num_ras)
            processed_annots.extend(final_ras)

    return processed_annots

# ============================================================================
# MAIN
# ============================================================================

def run_one_mode_logic(data, use_ca, use_vp):
    processed = []
    # Standard one-best selection
    by_vp_tid = defaultdict(lambda: defaultdict(list))
    for ann in data['annotations']:
        if has_negative_tracking_sentinel(ann):
            continue
        vp = ann.get('viewpoint', 'unknown') if use_vp else 'unknown'
        by_vp_tid[vp][ann['tracking_id']].append(ann)
    for vp, tracks in by_vp_tid.items():
        for tid, anns in tracks.items():
            anns.sort(key=lambda a: (get_ca_score(a), -a['frame_number']), reverse=True)
            processed.append(anns[0])
    return processed

def main():
    parser = argparse.ArgumentParser(description="KABR Unified Sampling - Final")
    parser.add_argument("in_json_path", type=str)
    parser.add_argument("json_final", type=str)
    parser.add_argument(
        "--sampling-config",
        type=str,
        default=None,
        help=(
            "Frame-sampling YAML to use for this run. Defaults to the pipeline's "
            "frame_sampling_config.yaml."
        ),
    )

    # Backward-compatible: old pipeline may still pass this
    parser.add_argument(
        "--json_stage1",
        type=str,
        default=None,
        help="Backward-compatible argument (optional). If provided, saves a copy of the output here."
    )

    args = parser.parse_args()

    config_path = args.sampling_config or path_from_file(__file__, "frame_sampling_config.yaml")
    cfg = load_config(config_path)
    random.seed(cfg['settings'].get('seed', 123456789))

    data = join_dataframe_dict(load_json(args.in_json_path))
    mode = cfg['settings'].get('selection_mode', 'many')
    use_ca = cfg['settings'].get('use_ca_score', True)
    use_vp = cfg['settings'].get('use_viewpoint', True)

    print(f"Using frame-sampling config: {config_path}")
    print(f"Sampling tracks using '{mode}' mode...")
    final_list = run_many_mode_logic(data, cfg) if mode == 'many' else run_one_mode_logic(data, use_ca, use_vp)

    # Save final output
    print(f"Saving {len(final_list)} annotations to {args.json_final}...")
    final_data = split_dataframe(pd.DataFrame(final_list))
    save_json(final_data, args.json_final)

    # If stage1 path is provided (old workflow), save a copy for compatibility
    if args.json_stage1:
        print(f"(Compat) Also saving stage1 copy to {args.json_stage1}...")
        save_json(final_data, args.json_stage1)

if __name__ == "__main__":
    main()
