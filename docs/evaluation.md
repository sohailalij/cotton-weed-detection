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

**Test set is frozen.** The images and labels never changed. It was meant to be
used once for the final numbers; see "Later experiments" at the end for where
that did not hold.

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
- 685 of the 845 test images come from one date (2021-09-10), so test scores
  largely describe one session and camera effects cannot be separated from
  session effects.
- The validation set has no Nikon or iPhone 11 Pro images and is 35% Canon, a
  camera with a single training image. Checkpoint selection therefore never saw
  two of the four main cameras.

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

## Later experiments (after the first test run)

The commitments above (test used once, no tuning on test) did not fully hold.
After the first test run I analysed test-set errors and used them to try two
changes. Each was then judged partly on test results, so the final test number
is not a completely untouched estimate. What was done:

1. **Error analysis on the test set** (`reports/error_analysis*`). Failures were
   counted by class, box size and camera, and cropped misses were inspected by eye.
2. **Split v3 (tried, rejected).** One date was moved from train to validation to
   put Nikon images in validation. Test mAP50 fell from 0.9055 to 0.8697 and
   failures rose from 151 to 250, mostly eclipta (23% of its training images were in
   the moved date). Split v1 was kept. Details in `docs/data_notes.md`.
3. **YOLO11s at 960 px on split v1.** Same settings otherwise, except batch size 8
   instead of 16, and 2.0 hours of training instead of 1.1.

### Results

Test split, `python -m weedlab.evaluate` (the 960 model with `--imgsz 960`).

| | YOLO11s 640 | YOLO11s 960 | YOLO11s 640, split v3 |
|---|---|---|---|
| mAP50 | 0.9055 | 0.9275 | 0.8697 |
| mAP50-95 | 0.8439 | 0.8714 | 0.8140 |
| Precision | 0.9458 | 0.9517 | 0.9081 |
| Recall | 0.7771 | 0.8374 | 0.7532 |
| CPU latency, median | 252.1 ms | 346.6 ms | 249.3 ms |
| CPU latency, 95th percentile | 315.8 ms | 375.1 ms | 316.1 ms |

On validation (815 images, same set for both) the 960 model also scored higher:
mAP50 0.894 against 0.881, and mAP50-95 0.826 against 0.822. That is the only
comparison not touched by test-set inspection, and it is a small difference from
a single run each.

**The 960 gain is concentrated in the small classes.** Of the summed per-class mAP50
gain, 84% comes from the six classes with about 50 test boxes or fewer (spotted
spurge, prickly sida, palmer amaranth, sicklepod, goosegrass, cutleaf groundcherry),
and 91% of the mAP50-95 gain. The six classes with more boxes gained 0.007 mAP50
and 0.005 mAP50-95 on average, and ragweed and carpetweed did not improve. The
aggregate gain should not be read as a general 2-point improvement.

### Error profile at a fixed confidence cutoff (845 images, 1,544 boxes)

| | 640 @ 0.25 | 960 @ 0.25 | 640 @ 0.15 | 960 @ 0.15 | 960 @ 0.58 |
|---|---|---|---|---|---|
| Correct | 1,393 | 1,381 | 1,413 | 1,401 | 1,319 |
| Confused (wrong species) | 51 | 33 | 55 | 37 | 23 |
| Missed | 100 | 130 | 76 | 106 | 202 |
| False positives | 375 | 194 | 556 | 313 | 60 |
| Failures on boxes under 64 px | 75 | 82 | 62 | 67 | 124 |
| Recall (correct / labelled boxes) | 0.902 | 0.894 | 0.915 | 0.907 | 0.854 |
| Precision (correct / all detections) | 0.766 | 0.859 | 0.698 | 0.800 | 0.941 |
| Detection F1 | 0.828 | 0.876 | 0.792 | 0.850 | 0.896 |

Precision here counts wrong-species detections as false alarms, and detection F1
is 2TP / (2TP + FP + FN) with a wrong-species detection counted as both a false
alarm and a miss, so these differ from the Ultralytics figures above. The 640 px
model was not run at 0.58.

At both matched cutoffs the 960 model finds about the same number of weeds as the
640 model (recall within one point) but makes roughly 200 fewer false detections,
and its detection F1 is 5 to 6 points higher. That, and not any recall gain, is what
drives its higher mAP. It fails slightly more often on boxes under 64 px, so there
is no evidence that the larger input size helps small weeds. The recall in the
headline table (0.837 against 0.777) is computed by Ultralytics at each model's own
F1-optimal cutoff and answers a different question.

The 0.58 column is the API default (see Decision). It was chosen from the
validation F1 curve before this run, and it also has the best detection F1 on
test. It trades recall for precision: 202 weeds are missed, with the largest
failure counts for carpetweed (67 of 293 boxes), waterhemp (47 of 385) and ragweed
(41 of 140).

### Main failure causes
1. Carpetweed is missed on clearly visible plants: 41 to 56 failures out of 293
   boxes in every model and cutoff tried. The cause is not established; the misses
   cluster in Nikon images.
2. Small weeds (under 64 px) are 18% of the boxes and about half of the failures
   of the first model. Ragweed and spotted spurge fail almost entirely at this size.
3. Look-alike species: the 640 model labelled eclipta, carpetweed, palmer amaranth
   and purslane as waterhemp (30 of its 51 confusions). The 960 model has fewer.

Some false positives may be unlabelled real weeds. Only a handful of images were
inspected, so this is not quantified.

### Decision
The 960 px model is carried into Phase 4 as the primary model. At matched
confidence cutoffs it finds about as many weeds as the 640 px model with roughly
half as many false alarms and fewer species mix-ups, and its detection F1 is 5 to 6
points higher. Against that, it does not find more weeds, does not help small
weeds, costs about 38% more CPU latency, and its mAP gain is concentrated in rare
classes. If ONNX Runtime latency on the hosting tier is a problem, the 640 px model
is a reasonable fallback.

The default confidence threshold for the API is 0.58, taken from the peak of the
F1-confidence curve on the validation set (all-classes F1 0.85 at 0.577; the curve
is nearly flat between about 0.25 and 0.75). The 0.25 versus 0.15 comparison above
is descriptive only. Carpetweed is the exception: its F1 on validation peaks near
0.14 and declines as the threshold rises, so carpetweed detections are the ones
most likely to be lost at the default.