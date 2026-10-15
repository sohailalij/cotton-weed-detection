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