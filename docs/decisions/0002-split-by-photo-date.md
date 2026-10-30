# 0002: Split the data by photo date

Date: 30 October 2026
Status: accepted

## Context

CottonWeedDet12 has no plot or scene IDs, and many photos of the same field on the same day look alike. A random split would put near-identical images in both training and test and inflate the scores.

## Decision

Assign whole photo dates to exactly one of train, validation or test (23 groups, seed 42). Split v1 gives train 3,988, validation 815 and test 845 images from 15, 5 and 3 groups. The manifest is `configs/split_v1.json`, and `python -m weedlab.prepare` rebuilds it and checks that it matches.

A second split (v3) moved one date, 176 images, from train to validation so that validation would contain Nikon images. Test mAP50 fell from 0.9055 to 0.8697 and failures rose from 151 to 250, mostly eclipta, because that date held 23% of eclipta's training images. v3 was rejected and v1 kept. It was one run per split, so the size of the drop is not precisely known.

## Consequences

- A difference-hash check found no near-duplicate pairs across splits on the same date. At a loose threshold there are 39 cross-split pairs on different dates. Two were inspected and showed different plants. The other 37 were not inspected.
- Date is only a proxy for scene. The same plant photographed on two days could still sit in two splits.
- Test covers only 3 sessions, and 685 of its 845 images come from one date, so test scores largely describe one session.
- Validation has no Nikon or iPhone 11 Pro images, so checkpoint selection never saw two of the four main cameras.