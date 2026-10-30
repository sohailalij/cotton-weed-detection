# 0005: Default confidence threshold of 0.58

Date: 30 October 2026
Status: accepted

## Context

The API needs a default confidence cutoff. The threshold must not be tuned on the test set, so it was chosen on validation.

## Decision

Use 0.58, the peak of the validation F1-confidence curve (all-classes F1 0.85 at 0.577). The curve is nearly flat between about 0.25 and 0.75. Users can change the cutoff with the `conf` query parameter and the slider in the web page.

## Consequences

- On test at 0.58 the 960 px model finds 1,319 of 1,544 labelled boxes (recall 0.854) with precision 0.941 and detection F1 0.896, the best of the cutoffs compared. It makes only 60 false detections, against 194 at 0.25.
- The price is 202 missed weeds, mostly carpetweed (67 of 293 boxes), waterhemp (47 of 385) and ragweed (41 of 140).
- Carpetweed is the exception to the rule. Its validation F1 peaks near 0.14, so its detections are the ones most likely to be lost at the default.
- Some false positives may be real weeds that were never labelled. Only a few images were inspected, so this is not quantified.