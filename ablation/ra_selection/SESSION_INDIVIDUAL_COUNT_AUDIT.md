# Session Individual-Count Audit

## Author Resolution (2026-07-30)

The lead author cross-referenced the selected giraffe videos and confirmed that
the manually curated species YAML files are the authoritative identity ground
truth. The conflicting giraffe counts in `session_events.csv` are erroneous and
must not be used to override or invalidate the YAML assignments. The paper
therefore reports the manually consolidated left/right identity counts,
verified cross-view links, and the resulting individual-count intervals.
Unlinked left/right clusters remain unresolved rather than being merged merely
to match session metadata.

## Scope

This audit compares the 13 experiment ground-truth files against
`session_events.csv`. Experiment folders were matched to session rows using the
complete DJI video-name set and verified against recording dates in the SRT
files. No ground-truth assignments were changed by this audit.

Every experiment contains only a subset of its matched session's videos.
Consequently, the session count is not the expected number that must appear in
the experiment subset. A ground-truth count below the session count can be
valid. A ground-truth count above the full-session count requires investigation.

## Counting Definitions

- **Current GT**: number of `individuals` entries in the species ground-truth
  YAML. Unlinked viewpoint-only clusters are currently counted as different
  individuals.
- **Cross-view minimum**: the smallest identity count obtainable by linking
  currently unmatched left and right identities, without merging two identities
  from the same viewpoint.
- **Documented count**: target-species count in `session_events.csv`. For the
  mixed Giraffe Experiment 13 session, this is four giraffes, not the total of
  ten animals (four giraffes and six Plains zebras).

## Comparison

| Experiment | Session event | Videos used/session | CSV count | Left IDs | Right IDs | Linked | Current GT | Cross-view minimum | Difference |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Grevy 1 | `19_01_2023_session_1` | 2/7 | 3 | 3 | 3 | 3 | 3 | 3 | 0 |
| Grevy 2 | `19_01_2023_session_3` | 2/7 | 3 | 2 | 1 | 0 | 3 | 2 | 0 |
| Grevy 3 | `19_01_2023_session_4` | 3/7 | 4 | 4 | 4 | 2 | 6 | 4 | +2 |
| Grevy 4 | `19_01_2023_session_6` | 3/7 | 3 | 3 | 3 | 3 | 3 | 3 | 0 |
| Grevy 5 | `20_01_2023_session_3` | 2/6 | 5 | 5 | 5 | 5 | 5 | 5 | 0 |
| Grevy 6 | `20_01_2023_session_4` | 3/7 | 4 | 4 | 4 | 4 | 4 | 4 | 0 |
| Plains 7 | `14_01_2023_session_3` | 3/12 | 17 | 4 | 4 | 3 | 5 | 4 | -12 |
| Plains 8 | `17_01_2023_session_1` | 2/3 | 5 | 5 | 2 | 1 | 6 | 5 | +1 |
| Plains 9 | `17_01_2023_session_2` | 2/6 | 5 | 5 | 2 | 1 | 6 | 5 | +1 |
| Plains 10 | `17_01_2023_session_4` | 3/13 | 4 | 4 | 4 | 4 | 4 | 4 | 0 |
| Plains 11 | `18_01_2023_session_6` | 4/7 | 10 | 7 | 8 | 3 | 12 | 8 | +2 |
| Giraffe 12 | `14_01_2023_session_2` | 3/5 | 2 | 5 | 6 | 3 | 8 | 6 | +6 |
| Giraffe 13 | `20_01_2023_session_1` | 3/6 | 4 giraffes | 5 | 6 | 3 | 8 | 6 | +4 |

The machine-readable version is
[`session_individual_count_audit.csv`](session_individual_count_audit.csv).

## Findings

### Counts that agree

Grevy Experiments 1, 2, 4, 5, and 6 and Plains Experiment 10 have current GT
counts equal to the session metadata. Since each experiment uses only part of
the session, agreement supports consistency but does not independently prove
that every identity linkage is correct.

### Plains Experiment 7 is not contradictory

The experiment uses only DJI videos 0059-0061 from a 12-video session containing
17 Plains zebras. Five manually established identities in this smaller temporal
subset are plausible. The metadata cannot establish how many of the 17 animals
appear in these three videos.

### Four zebra discrepancies can be explained by missing cross-view links

- Grevy 3 has four left and four right identities but only two links. Two
  additional left-right links would reduce the current count from six to the
  documented four.
- Plains 8 has one unmatched right identity. One additional link would reduce
  six identities to the documented five.
- Plains 9 has one unmatched right identity. One additional link would reduce
  six identities to the documented five.
- Plains 11 needs two additional links to reduce 12 identities to the documented
  ten. Up to four additional links are structurally possible.

The counts identify how many links may be missing, but they do not identify the
correct pairs. Those pairs still require visual or metadata-supported review.

### The giraffe discrepancies are not cross-view problems alone

Giraffe 12 has five manually distinct left identities and six manually distinct
right identities. Even maximal cross-view linkage leaves at least six
individuals, while the session metadata explicitly reports two giraffes and
describes a white female and a caramel male calf. At least four within-view
identity distinctions or the session count itself must therefore be wrong.

Giraffe 13 has a cross-view minimum of six versus four documented giraffes. The
session is mixed, with four giraffes and six Plains zebras. At least two
within-view distinctions, species assignments, or the documented count require
revision.

These two ground-truth files should not be treated as count-validated until the
within-view clusters are re-audited against full temporal contact sheets.

## Species-Pipeline Check

The session species mapping agrees with the experiment labels for Grevy 1-6,
Plains 7-11, and Giraffe 12. Giraffe 13 comes from a mixed session, so its target
comparison must use four giraffes rather than all ten animals.

BioCLIP initially predicted multiple classes:

- Giraffe 12: 64,318 giraffe predictions and 3,006 predictions from Plains
  zebra, Grevy's zebra, or `neither`.
- Giraffe 13: 29,396 giraffe predictions and 36,886 predictions from Plains
  zebra, Grevy's zebra, or `neither`.

The viewpoint stage retained only the two configured giraffe classes before IA
filtering. This is label-based filtering, not manual species verification. The
configured species `confidence_threshold: 0.75` is not applied by
`species_identifier.py`, and the BioCLIP prediction score is not retained in the
saved annotation JSON. Therefore, species-predicted giraffe crops, especially
from mixed Giraffe 13, should receive a visual species audit before release.

## Recommended Actions

1. Review unmatched cross-view identities for Grevy 3 and Plains 8, 9, and 11.
   Use the session counts as a consistency constraint, not as automatic proof
   that a particular pair must merge.
2. Re-audit every within-view identity in Giraffe 12 and 13 using temporal
   contact sheets. Check both identity and species for Giraffe 13.
3. Preserve both fields in the released data:
   `session_individual_count_metadata` and `visible_subset_identity_count_gt`.
   They measure different things and should not be forced to agree.
4. Treat session counts as contextual metadata until frame-level review confirms
   which animals occur in the selected video subset.
5. Do not revise the ground-truth YAMLs solely to make their counts match the
   session document.
