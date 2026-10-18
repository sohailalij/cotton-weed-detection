# Baseline: YOLO11n, 50 epochs

Trained on Google Colab (Tesla T4) in 1.02 hours, about 63 s per epoch.
Ultralytics 8.4.181, PyTorch 2.11.0+cu130. The exact settings are in `args.yaml`.

```python
YOLO("yolo11n.pt").train(
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

All classes: precision 0.856, recall 0.774, mAP50 0.853, mAP50-95 0.784.

| Class | Images | Boxes | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| waterhemp | 187 | 235 | 0.897 | 0.881 | 0.949 | 0.919 |
| morning_glory | 221 | 244 | 0.918 | 0.881 | 0.936 | 0.829 |
| purslane | 134 | 271 | 0.826 | 0.787 | 0.865 | 0.761 |
| spotted_spurge | 69 | 84 | 0.941 | 0.750 | 0.830 | 0.740 |
| carpetweed | 16 | 21 | 0.639 | 0.422 | 0.526 | 0.434 |
| ragweed | 132 | 300 | 0.924 | 0.807 | 0.898 | 0.787 |
| eclipta | 59 | 93 | 0.911 | 0.817 | 0.925 | 0.895 |
| prickly_sida | 36 | 39 | 0.738 | 0.872 | 0.851 | 0.786 |
| palmer_amaranth | 36 | 38 | 0.782 | 0.789 | 0.847 | 0.829 |
| sicklepod | 23 | 26 | 0.932 | 1.000 | 0.971 | 0.971 |
| goosegrass | 22 | 27 | 0.956 | 0.889 | 0.972 | 0.851 |
| cutleaf_groundcherry | 28 | 31 | 0.808 | 0.387 | 0.671 | 0.604 |

## Notes

- These are validation numbers. The best checkpoint was selected on this same
  set, so they are slightly optimistic. The test set has not been used.
- Per-class scores rest on 21 to 31 boxes for the thinnest classes and are noisy.
- Curves are still improving at epoch 50, so the model is probably under-trained.
- Most errors are one species mistaken for another, not missed plants. Cutleaf
  groundcherry is mostly called Palmer amaranth or prickly sida. Waterhemp is
  partly called Palmer amaranth or eclipta. See `confusion_matrix_normalized.png`.
- Weights (`best.pt`, 5.3 MB) are on Google Drive and not committed.