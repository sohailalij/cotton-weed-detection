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

## Model selection (written before the test set was evaluated)

Both baselines were trained with identical settings (`configs/train_yolo11n.yaml`
and `configs/train_yolo11s.yaml`) and compared on the validation set only.
YOLO11s scored higher on every headline metric (mAP50 0.881 versus 0.853,
mAP50-95 0.822 versus 0.784), so YOLO11s is the model carried forward.

Both models are evaluated on the test set once, for reporting. Test results
will not be used to change the model choice, the hyperparameters, or the
confidence threshold; any threshold used in the API is chosen on validation.

Inference speed is measured separately. If CPU latency makes YOLO11s unusable
for free-tier hosting, that is a deployment constraint and will be recorded
here as its own decision, not as a test-set result.

## Results (Phase 3)

Test split, evaluated once per model with `python -m weedlab.evaluate` on the
frozen split (845 images, 3 photo sessions). Every number below is copied from
`reports/test_eval/<model>/metrics.json`. Ultralytics 8.4.181, PyTorch 2.14.1 (CPU).

| | YOLO11n | YOLO11s |
|---|---|---|
| mAP50 | 0.8865 | 0.9055 |
| mAP50-95 | 0.8237 | 0.8439 |
| Precision | 0.8866 | 0.9458 |
| Recall | 0.8025 | 0.7771 |
| CPU latency, median | 63.2 ms | 252.1 ms |
| CPU latency, 95th percentile | 109.0 ms | 315.8 ms |

mAP50 and mAP50-95 are averaged over the 12 classes. Precision and recall are
reported at the confidence threshold Ultralytics selects, so they say less about
the models than mAP does. Latency is one image at a time with PyTorch on the
development laptop's CPU, measured on the resized 1024 px copies, so it excludes
the cost of decoding and shrinking a full-size phone photo.

### Per class

| Class | Images | Boxes | mAP50 n | mAP50 s | mAP50-95 n | mAP50-95 s |
|---|---|---|---|---|---|---|
| waterhemp | 291 | 385 | 0.9535 | 0.9498 | 0.9012 | 0.9087 |
| morning_glory | 137 | 147 | 0.9735 | 0.9854 | 0.8779 | 0.9138 |
| purslane | 85 | 103 | 0.9747 | 0.9769 | 0.9423 | 0.9390 |
| spotted_spurge | 29 | 48 | 0.7636 | 0.8469 | 0.6948 | 0.7745 |
| carpetweed | 169 | 293 | 0.8968 | 0.9003 | 0.7827 | 0.7935 |
| ragweed | 78 | 140 | 0.8143 | 0.8387 | 0.6844 | 0.7226 |
| eclipta | 182 | 302 | 0.9633 | 0.9719 | 0.9160 | 0.9327 |
| prickly_sida | 27 | 31 | 0.8763 | 0.9110 | 0.8174 | 0.8639 |
| palmer_amaranth | 45 | 51 | 0.9408 | 0.9278 | 0.9271 | 0.8938 |
| sicklepod | 8 | 9 | 0.9730 | 0.9337 | 0.8548 | 0.8044 |
| goosegrass | 21 | 22 | 0.8550 | 0.7608 | 0.8329 | 0.7450 |
| cutleaf_groundcherry | 12 | 13 | 0.6534 | 0.8631 | 0.6534 | 0.8352 |

### What the numbers support

- YOLO11s is ahead on mAP by about 2 points, but the gap is concentrated in one
  class. Cutleaf groundcherry (13 test boxes) accounts for nearly all of the mAP50
  difference and about three quarters of the mAP50-95 difference. Without it the
  average mAP50 gain is about 0.002 and classes differ in both directions.
- The models are roughly tied on mAP50 for the classes with the most boxes
  (waterhemp, eclipta, carpetweed).
- Ragweed is the weakest class with a meaningful number of boxes (140) for both models.
- Classes with about 50 test boxes or fewer (spotted spurge, prickly sida,
  palmer amaranth, sicklepod, goosegrass, cutleaf groundcherry) differ between the
  models by up to 21 points of mAP50 and should not be compared one by one.
- Test scores are higher than validation scores for both models. The class mix
  differs (carpetweed has 293 test boxes and 21 validation boxes), so validation
  numbers did not predict the test numbers well.
- YOLO11s is about 4 times slower on this CPU. Whether that matters is decided in
  Phase 4 after ONNX export.

## Decision

YOLO11s remains the primary model, as written before the test run. The test results
do not change that choice, but they show the accuracy advantage is small. YOLO11n
stays as the fallback if CPU latency on the hosting tier is a problem. That is a
deployment decision for Phase 4, made from ONNX Runtime latency measurements and
not from test accuracy.