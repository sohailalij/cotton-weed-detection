# Evaluation

## Data and split (Phase 1)

**Dataset.** CottonWeedDet12: 5,648 close-up photos of single weed plants on
bare soil, 12 species, 9,370 boxes. License on the Hugging Face card is
CC BY-NC 4.0, so this project is non-commercial.

**Labels.** Rebuilt from the VGG JSON files. The shipped YOLO files had 18
extra boxes in 14 images (all from the 2021-09-03 session); two were checked
by eye and sat on bare soil or on a plant already labeled as another species.

**Split.** Whole photo dates go to exactly one of train, validation, or test
(23 groups, seed 42). Result: train 3,988 / val 815 / test 845 images from
15 / 5 / 3 groups. The manifest is `configs/split_v1.json`, and
`python -m weedlab.prepare --root <raw data folder>` rebuilds it from scratch
and checks that it matches.

**Test set is frozen.** It is used once, for the final numbers. All tuning
happens on validation.

**Leakage check.** Difference hashes of all images, compared across splits.
At the strict threshold, every near-duplicate pair is inside one split and
one date. At a loose threshold, 39 cross-split pairs on different dates
appear; the two inspected pairs showed different plants on different soil.
The other 37 were not inspected.

## Limitations

- The dataset has no plot or scene IDs. Grouping by date is a proxy, so the
  same plant photographed on two different days could still sit in two splits.
- Test covers only 3 photo sessions. Results describe those conditions, not
  other seasons, sites, or cameras.
- Some classes are thin in the held-out sets: 8 Sicklepod and 12 Cutleaf
  groundcherry test images, 16 Carpetweed validation images. Per-class scores
  for these are noisy and are reported with image counts.
- Every image contains at least one weed. The model never saw a weed-free
  field, so false-alarm behavior on clean images is unmeasured.
- All images are close-ups of a single plant. Wide field or drone views are
  out of scope.

## Results (Phase 3)

To be filled in after training and evaluation.