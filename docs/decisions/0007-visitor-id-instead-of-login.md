# 0007: Separate visitors with a random id, not a login

Date: 30 October 2026
Status: accepted

## Context

The service saves a resized copy of every uploaded photo, so visitors must not see each other's detections. A login would add accounts, passwords and password reset for a portfolio demo.

## Decision

The browser makes a random 128-bit id on first use, keeps it in `localStorage` and sends it in the `X-Visitor-Id` header. The API stores it with each detection and only returns, counts or deletes rows with the same id. Someone else's detection gets the same 404 as one that does not exist. Detections and photos are deleted after 7 days by default.

## Consequences

- This stops accidental viewing but is not access control. Anyone who has an id can read and delete that visitor's data.
- The image route accepts the id as a query parameter, because an `<img>` tag cannot send headers. That means the id can appear in access logs of the API host and any proxy in front of it.
- Clearing site data or switching browser starts an empty history.
- Anyone can invent an id, so it is not a quota. The rate limit counts requests per client address instead (see 0008).
- The README and the web page tell visitors not to upload anything private.