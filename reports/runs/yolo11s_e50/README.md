# Baseline: YOLO11s, 50 epochs

Trained on Google Colab (Tesla T4) in 1.14 hours, about 71 s per epoch.
Ultralytics 8.4.181, PyTorch 2.11.0+cu130. The exact settings are in `args.yaml`.
Identical to the YOLO11n run (`../yolo11n_e50`) except for the model size.

```python
YOLO("yolo11s.pt").train(
    data="/content/data.yaml",
    epochs=50,
    imgsz=640,
    batch=16,
    workers=2,
    cache="disk",
    patience=15,
    seed=42,
)
```

Data: `data/yolo`, resized copy (long side 1024 px) of the frozen split in
`configs/split_v1.json`. Labels rebuilt from the VGG JSON.

## Validation results (best checkpoint)

All classes: precision 0.909, recall 0.787, mAP50 0.881, mAP50-95 0.822.

| Class | Images | Boxes | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| waterhemp | 187 | 235 | 0.929 | 0.896 | 0.963 | 0.932 |
| morning_glory | 221 | 244 | 0.948 | 0.881 | 0.951 | 0.863 |
| purslane | 134 | 271 | 0.876 | 0.832 | 0.905 | 0.807 |
| spotted_spurge | 69 | 84 | 0.947 | 0.798 | 0.884 | 0.794 |
| carpetweed | 16 | 21 | 0.719 | 0.381 | 0.541 | 0.428 |
| ragweed | 132 | 300 | 0.941 | 0.833 | 0.926 | 0.813 |
| eclipta | 59 | 93 | 0.982 | 0.925 | 0.960 | 0.925 |
| prickly_sida | 36 | 39 | 0.907 | 0.769 | 0.900 | 0.850 |
| palmer_amaranth | 36 | 38 | 0.902 | 0.730 | 0.859 | 0.852 |
| sicklepod | 23 | 26 | 0.956 | 1.000 | 0.978 | 0.978 |
| goosegrass | 22 | 27 | 0.959 | 0.861 | 0.967 | 0.909 |
| cutleaf_groundcherry | 28 | 31 | 0.847 | 0.536 | 0.743 | 0.717 |

## Comparison with YOLO11n (validation, one run each)

| | YOLO11n | YOLO11s |
|---|---|---|
| Precision | 0.856 | 0.909 |
| Recall | 0.774 | 0.787 |
| mAP50 | 0.853 | 0.881 |
| mAP50-95 | 0.784 | 0.822 |
| Parameters | 2.6M | 9.4M |
| Weights file | 5.3 MB | 19.2 MB |
| Inference per image (T4) | 2.7 ms | 10.5 ms |
| Training time | 1.02 h | 1.14 h |

## Notes

- These are validation numbers. The best checkpoint was selected on this same
  set, so they are slightly optimistic. The test set has not been used.
- One run per model with one seed. Validation mAP moves by 1 to 2 points between
  epochs, so small differences are not conclusive. The gap between the two models
  (about 3 points mAP50, 4 points mAP50-95) is larger than that but is still a
  single comparison.
- Cutleaf groundcherry improved the most (recall 0.39 to 0.54). Carpetweed is
  still the weakest class (mAP50 0.54, recall 0.38).
- Per-class scores for the thinnest classes rest on 21 to 38 boxes and are noisy.
- Weights (`best.pt`, 19.2 MB) are on Google Drive and not committed.