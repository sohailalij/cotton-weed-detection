# Model card: cotton weed detector

## Model
YOLO11s object detector (about 9.4 million parameters) fine-tuned from the Ultralytics pretrained weights on CottonWeedDet12. Trained at 960px for 50 epochs (seed 42, batch 8, AdamW chosen automatically, early stopping patience 15, which did not trigger) on a free Colab T4 in about 2 hours. Output: a box, a species label (one of 12) and a confidence for each detected weed.

## Intended use
Research and portfolio demonstration of weed detection in close-up photos of cotton plants, for example a scout counting weed species in a photo. A human should review the output.

## How it is served
The model is exported to ONNX and run with ONNX Runtime on a CPU. On all 845 test images at confidence 0.58 it agrees with the PyTorch model on 99.1% of detections. The public demo runs on free hosting, so a detection takes about 15 seconds, and uploaded photos are deleted after 7 days. There is no login, so do not upload private photos.

## Training and evaluation data
CottonWeedDet12 (Dang et al. 2023; Zenodo record 7535814): 5,648 images and 9,370 boxes across 12 weed species, taken with smartphones and hand-held cameras in southern US cotton fields from June to September 2021. Every image contains at least one weed, and there are no weed-free images. Images were split by photo date (v1 manifest, `configs/split_v1.json`): 3,988 train, 815 validation, 845 test.

## Performance (test split, 845 images)
mAP@50 0.928, mAP@50-95 0.871, precision 0.952, recall 0.837. Precision and recall here are computed by Ultralytics at the model's own best-F1 cutoff, so they differ from the figures at the API default of 0.58 given under failure modes below. Per-class results, error analysis and latency are in `docs/evaluation.md`. The gain over the same model at 640 px is concentrated in the rarer classes; on the six largest classes the two are nearly tied. At matched cutoffs the 960 px model finds about as many weeds as the 640 px one but makes far fewer false detections.

The test set was used to guide the move from 640 px to 960 px, so these numbers are not a completely untouched estimate. `docs/evaluation.md` explains what was done.

## Known failure modes
- Carpetweed is missed frequently even when the plant is clearly visible. At the default confidence of 0.58, 67 of its 293 test boxes were missed or mislabelled, so about 77% were found correctly.
- Small weeds are missed far more often than large ones. At 0.58, 124 of the 271 test boxes under 64 px failed (46%), against 101 of the 1,273 larger ones (8%).
- Ragweed is the weakest class with a meaningful number of boxes. At 0.58, 41 of its 140 test boxes failed, so about 71% were found correctly.
- Eclipta, carpetweed, palmer amaranth and purslane are sometimes labelled as waterhemp, mostly at lower confidence.
- Rare classes (sicklepod, cutleaf groundcherry, goosegrass, prickly sida) have few test examples, so their scores are uncertain.
- The confidence threshold trades missed weeds against false alarms. At the default of 0.58 (the peak of the validation F1 curve) the model found 85% of the labelled weeds with 94% precision on the test set; 202 weeds were missed, mostly carpetweed, waterhemp and ragweed. At 0.25 it found 89% with 86% precision.
- Every training and test image contains at least one weed, so behaviour on weed-free photos is unmeasured. Expect false alarms on clean soil that the test numbers do not show.

## Not for
- Herbicide or spraying decisions, or any automated action without human review.
- Other crops, other regions or seasons, wide field views, or drone imagery. The training data is close-up single-plant photos from one region and one growing season, and the model has not been tested on anything else.
- Counting plants precisely or measuring weed density from uncalibrated photos.
- Commercial use (see licensing).

## Data limitations
- Test scores mostly reflect one photo session (685 of 845 images share a date).
- The validation set has no Nikon or iPhone 11 Pro images and is 35% Canon, a camera with one training image. Details in `docs/data_notes.md`.
- Labels come from the dataset authors. Some unlabelled weeds may exist, which would count as false positives.

## Licensing
- Ultralytics YOLO is released under AGPL-3.0.
- The dataset is licensed CC BY-NC 4.0 (non-commercial), according to its Hugging Face dataset card. Anything trained on it should be treated as non-commercial unless the rights holders give separate permission.
- Citation: Dang, F., Chen, D., Lu, Y., Li, Z. (2023). YOLOWeeds: A novel benchmark of YOLO object detectors for multi-class weed detection in cotton production systems. Computers and Electronics in Agriculture 205, 107655. Dataset DOI: 10.5281/zenodo.7535814.