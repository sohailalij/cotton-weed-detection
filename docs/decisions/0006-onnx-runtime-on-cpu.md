# 0006: Serve the model with ONNX Runtime on CPU

Date: 30 October 2026
Status: accepted

## Context

The API has to run on a free host with no GPU, and the PyTorch and Ultralytics stack is heavy to ship.

## Decision

Export the 960 px model to ONNX (38.2 MB, dynamic height and width) and run it with ONNX Runtime through `src/weedlab/inference.py`, which needs only NumPy, Pillow and ONNX Runtime.

## Consequences

- Agreement with PyTorch on all 845 test images at confidence 0.58: PyTorch makes 1,403 detections and ONNX makes 1,398. Of those, 1,390 match in both directions (same class, box overlap of at least 0.9), which is 99.1% of the PyTorch detections. The largest confidence difference between matched detections is 0.076.
- ONNX Runtime was faster than PyTorch in all three runs, by 1.9, 1.9 and 2.9 times. The ratio changed between runs and the cause was not isolated. In the quietest run (50 images, confidence 0.58) the median was 166 ms against 473 ms. That is one run on a development laptop and says nothing about hosted hardware.
- On the free Render instance, which has a tenth of a CPU, a detection takes about 15 seconds.
- The model file is not in the repository. The API downloads it at startup and refuses to start if its SHA-256 does not match.