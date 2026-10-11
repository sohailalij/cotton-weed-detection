# Product brief: cotton weed detection service

## Who it's for
An agronomist or crop scouting service that checks cotton fields for weed
pressure. They walk fields or fly drones, take lots of photos, and currently
review them by eye, which is slow and inconsistent.

## What they do
Upload a photo of a cotton field to the web app (or send it to the API).

## What they get back
- Boxes drawn around each detected weed, labeled by species
- A confidence score for each box, with a slider to hide low-confidence ones
- A weed coverage figure: the share of the image covered by weeds
- A history of past uploads and simple charts of species counts over time

## What this is not
- It does not recommend herbicides or any spraying decision
- It does not control drones or work in real time
- It is not validated outside its training data (one dataset, one region),
  so it should not be trusted on other crops, lighting, or growth stages

## How I'll know it works
- Detection quality is measured on a held-out test set that shares no
  near-duplicate images with the training data
- Per-species results are reported, so weak classes are visible
- The API rejects bad uploads and the service is deployed with a runbook

## Known limits
Free hosting means slow cold starts and CPU-only inference. This is a
portfolio project, not a farming tool.