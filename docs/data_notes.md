# Data notes

## Dataset
CottonWeedDet12: 5,648 images, 12 weed classes, close-up photos of single
plants on bare soil (phones and hand-held cameras, summer 2021).
License on the Hugging Face card: CC BY-NC 4.0 (non-commercial). Confirm on Zenodo.

## Findings from the audit
- Every image has at least one weed. There are no negative (weed-free) images.
- Class imbalance is large: 111 images (Cutleaf groundcherry) to 1,413 (Waterhemp).
- Image sizes vary (3024x4032 up to 4000x6000). EXIF orientation is 1 on all files.
- Class ids were verified against species names in the VGG JSON files.

## Label discrepancy
The shipped YOLO files contain 9,388 boxes, the VGG JSON files contain 9,370.
The 18 extra boxes are in 14 images, all from the 20210903 session. Overlays of
two of them show boxes on bare soil or on a plant already labeled as another
species. I treat the JSON as the source of truth and regenerate YOLO labels
from it (src/weedlab/convert_labels.py).

## Limits
Close-up single-plant images only. The model is not validated on wide field
views, drone imagery, or other regions or seasons.

## Split
Grouped by photo date (23 groups) so a session never spans two splits.
Split v1 (seed 42): train 3,988 / val 815 / test 845 images, from 15 / 5 / 3 groups.
Test has only 8 Sicklepod and 12 Cutleaf groundcherry images, so per-class
results for those are noisy. Test covers only 3 sessions.
Stray YOLO boxes removed from the JSON-based labels cost Cutleaf groundcherry
7 images (104 real versus 111 in the shipped labels).

## Leakage check
Difference-hash comparison of all images against the split manifest.
At distance <= 6 there are 10 near-duplicate pairs, all within a single split
and a single date. At distance <= 12 there are 39 cross-split pairs on
different dates. I viewed the two most suspicious ones and they show
different plants on different soil, matched only because they are the same
species photographed from above. I did not inspect the other 37. Split v1 is
kept. The date grouping remains the main protection against leakage.

## Split v3 (tried and rejected)

**Why I tried it.** The v1 split (grouped by date) left the validation set with no Nikon or iPhone 11 Pro images, and 35% of it is Canon, a camera with a single training image. Checkpoint selection therefore never saw two of the four main cameras in the test set.

**What I changed.** Starting from v1, I moved one whole date (`20210909`, 176 images, 129 of them Nikon) from train to validation. The test set was left identical, so results stay comparable. Manifest: `configs/split_v3.json`.

**What happened.** Same model and settings (YOLO11s, 640px, seed 42), one run each:

| | v1 split | v3 split |
|---|---|---|
| Test mAP50 | 0.9055 | 0.8697 |
| Test mAP50-95 | 0.8439 | 0.8140 |
| Test failures (misses + confusions) | 151 | 250 |
| Eclipta failures | 25 | 84 |

The date I moved held 78 of eclipta's 335 training images (23%), more than any other class lost, and eclipta accounts for most of the regression (mostly eclipta predicted as waterhemp or prickly sida). Failures rose on iPhone SE as well as Nikon, so it was not a Nikon-specific effect.

**Decision.** Keep v1. This is one run per split, so the size of the drop is not precisely known, but the pattern fits the explanation and I did not want to build on a split that produced a weaker model.

**Limitations of v1 that remain.**
- Validation contains no Nikon or iPhone 11 Pro images, so checkpoint selection did not see them.
- 685 of the 845 test images come from one date (`20210910`). Test metrics largely describe one session, and camera effects cannot be separated from session effects.