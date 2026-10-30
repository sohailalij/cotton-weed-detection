# 0003: Use YOLO11s as the primary model

Date: 30 October 2026
Status: accepted

## Context

Two model sizes were candidates, YOLO11n and YOLO11s. Both were trained with identical settings and compared on the validation set only. The choice was written down before the test set was evaluated.

## Decision

Carry YOLO11s forward. On validation it scored higher on every headline metric (mAP50 0.881 against 0.853, mAP50-95 0.822 against 0.784).

## Consequences

- On the test set YOLO11s is ahead by about 2 points of mAP50 (0.9055 against 0.8865), but nearly all of that gap comes from one class, cutleaf groundcherry, which has 13 test boxes. Without it the average gain is about 0.002.
- YOLO11s is about 4 times slower on the development laptop's CPU in PyTorch (median 252 ms against 63 ms). Whether that matters was left to the ONNX measurements.
- YOLO11n stays as the fallback if latency on the hosting tier becomes a problem.
- The accuracy advantage is small, and the record says so. The choice rests on the validation comparison made before the test run.