# Cotton weed detection

Upload a close-up photo of a cotton field and get back bounding boxes, species labels and a weed coverage estimate for 12 weed species. A YOLO11s detector trained on CottonWeedDet12, served through a FastAPI service with ONNX Runtime on CPU, with detection history stored in Postgres, and a React page to use it.

**Status:** data pipeline, training, evaluation, the API, the web page and the public deployment are done. The live demo runs on free hosting, see below for what that means.

## Live demo

- Web page: https://cotton-weed-detection.vercel.app
- API: https://cotton-weed-detection.onrender.com (interactive docs at `/docs`)

It runs entirely on free tiers: the web page on Vercel, the API in a Docker container on Render, and the database on Neon. The model file is kept in a Hugging Face model repository ([sohail187/cotton-weed-yolo11s](https://huggingface.co/sohail187/cotton-weed-yolo11s)). The API downloads it at startup and checks its SHA-256 before using it.

What to expect from free hosting:

- The API sleeps when idle, so the first request after a quiet period can take about 50 seconds.
- A detection typically takes about 15 seconds, because the free instance has a tenth of a CPU.
- The database also pauses when idle and adds a few seconds when it wakes.
- Photos are deleted after 7 days and there is no login, so do not upload anything private (see [Privacy](#privacy)).

Pushing a version tag such as `v0.1.2` deploys that exact commit to Render through a GitHub Actions workflow. Merging to `main` does not deploy. How to deploy, roll back and debug is in [`docs/runbook.md`](docs/runbook.md).

A diagram of how the pieces fit together is in [`docs/architecture.md`](docs/architecture.md).

## Results

Held-out test set (845 images, 1,544 boxes, whole photo dates kept in one split to avoid leakage):

| Model | mAP50 | mAP50-95 |
|---|---|---|
| YOLO11n, 640 px | 0.8865 | 0.8237 |
| YOLO11s, 640 px | 0.9055 | 0.8439 |
| **YOLO11s, 960 px (served)** | **0.9275** | **0.8714** |

At the API's default confidence of 0.58 (chosen from the validation F1 curve) the 960 px model found 85% of labelled weeds with 94% precision on the test set. The ONNX export is about twice as fast as PyTorch on the same CPU and agrees with it on 99% of detections. Full tables, error analysis and the experiments that did not work (a rebalanced split, larger input size for small weeds) are in [`docs/evaluation.md`](docs/evaluation.md). Intended use and failure modes are in [`docs/model_card.md`](docs/model_card.md).

## Run it

You need Docker. The trained model is not in the repository. Place the exported file at `models/yolo11s_v1_960.onnx`; it is produced from the checkpoint with:

```
python -m weedlab.export --weights models/yolo11s_v1_960_best.pt --imgsz 960 --out models/yolo11s_v1_960.onnx
```

Instead of exporting it yourself, the API can download the published file. Set `WEEDLAB_MODEL_URL` to the pinned address in the model repository and `WEEDLAB_MODEL_SHA256` to its hash. If the file is missing at startup the API downloads it, and it refuses to start if the hash does not match.

Then start the API and the database:

```
docker compose up --build
```

The service listens on `http://localhost:8000`, applies the database migrations on startup, and serves interactive docs at `/docs`. Try it (the visitor id is explained under [Privacy](#privacy); any 16 to 64 letters, digits, `_` or `-` will do):

```
curl -H "X-Visitor-Id: my-test-visitor-0001" -F "file=@photo.jpg" "http://localhost:8000/v1/detect?conf=0.58"
```

| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/detect` | Upload an image; returns boxes, species, scores and box coverage, and saves the result with a resized copy of the photo |
| GET | `/v1/detections` | Paginated history, newest first |
| GET | `/v1/detections/{id}` | One saved result |
| GET | `/v1/detections/{id}/image` | The saved photo as a JPEG, at most 640 px on the long side |
| DELETE | `/v1/detections/{id}` | Delete a saved result and its photo |
| GET | `/v1/stats` | Species counts and mean coverage, optionally between `start` and `end` |
| GET | `/v1/stats/daily` | One entry per day that has detections, with detections, weeds found, mean coverage and species counts; days are UTC days; optionally between `start` and `end` |
| GET | `/v1/model` | Model name, input size, classes and test metrics |
| GET | `/health` | Liveness |

Every route under `/v1/detect`, `/v1/detections` and `/v1/stats` needs the `X-Visitor-Id` header and only ever returns that visitor's own data. `/v1/model` and `/health` do not. The image route also accepts the id as a `visitor` query parameter, because an `<img>` tag cannot send headers.

Uploads are limited to JPEG, PNG and WEBP, decoded rather than trusted by header, 15 MB and 50 million pixels by default. `/v1/detect` is rate limited per client.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `WEEDLAB_MODEL_PATH` | required | Path to the ONNX model |
| `WEEDLAB_DATABASE_URL` | required | SQLAlchemy URL, for example `postgresql+psycopg://user:pass@host:5432/db` |
| `WEEDLAB_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins; `*` is refused |
| `WEEDLAB_MAX_UPLOAD_MB` | `15` | Upload size limit |
| `WEEDLAB_RATE_LIMIT_PER_MINUTE` | `10` | Requests per client per minute on `/v1/detect` |
| `WEEDLAB_RETENTION_DAYS` | `7` | Saved detections and photos older than this many days are deleted automatically; `0` keeps everything |
| `WEEDLAB_MODEL_URL` | unset | https address to download the model from when the file is missing |
| `WEEDLAB_MODEL_SHA256` | unset | Expected SHA-256 of the model file. Required when downloading; a mismatch stops the service |
| `WEEDLAB_TRUSTED_PROXY_HOPS` | `0` | Number of trusted proxies in front of the API. The visitor's address is read that many entries from the right of `X-Forwarded-For`. It is `3` on Render and `0` locally |

The service refuses to start if a required setting is missing or a value is invalid. The credentials in `docker-compose.yml` are for local development only.

### Run the web page

With the API running, in another terminal:

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The page talks to `http://127.0.0.1:8000` unless `VITE_API_URL` says otherwise. Use `localhost`, not another address of the same computer, unless you have added that origin to `WEEDLAB_CORS_ORIGINS`.

## Privacy

The service saves a resized copy of every photo you upload, so it separates visitors from each other.

- **How it works.** The first time the page is opened, the browser makes a random 128-bit id and keeps it in `localStorage`. It sends that id with every request. The API stores it with each detection and returns, counts and deletes only rows with the same id. A detection that belongs to someone else gets the same 404 as one that does not exist, so nobody can probe for ids.
- **What it is not.** It is not a login. Anyone who has your id can read and delete your detections, and the id is the only thing protecting them. It is random and long enough that it cannot be guessed. Clearing the browser's site data, or using another browser or device, starts an empty history, and the old rows stay unreachable until they expire.
- **Where the id can leak.** The thumbnail URLs carry the id in the query string, so it can appear in access logs of the API host and any proxy in front of it. Do not share a screenshot or a copied image address if you want the history to stay private.
- **Automatic deletion.** Detections and their photos older than `WEEDLAB_RETENTION_DAYS` (7 by default) are deleted for every visitor. The cleanup runs when the service starts and then at most once an hour while it is running. `0` turns it off.
- **Older rows.** Detections saved before visitor ids existed have an empty id, so no visitor can see them. They are removed by the same cleanup once they pass the retention age.
- **Rate limiting is separate.** The limit on `/v1/detect` counts requests per client address, not per visitor id. Anyone can invent an id, so the id is not a quota.

### Trying it from a phone on the same network

The service has no login, so do this only on a network you trust, and only for as long as you need it.

1. Find the computer's address on the Wi-Fi network, for example `192.168.0.125`.
2. Start the API with that origin allowed. In PowerShell:
   `$env:WEEDLAB_CORS_ORIGINS = "http://localhost:5173,http://<address>:5173"` and then `docker compose up -d`. Compose passes the variable to the service, and without it only `http://localhost:5173` is allowed.
3. In the `frontend` folder, start the page for the network with `$env:VITE_API_URL = "http://<address>:8000"` and `npm run dev -- --host`.
4. In the operating system firewall, allow incoming connections to ports 5173 and 8000 from the phone's address only, and remove the rule afterwards.
5. Open `http://<address>:5173/` on the phone.

The phone gets its own visitor id, so its history is separate from the computer's. Anyone who can reach port 8000 can still upload photos and use the computer's processor, which is why the firewall rule should be limited to one device and removed after the test. On a shared network, some routers also block devices from reaching each other, in which case a phone hotspot is an alternative.

## Develop

```
pip install -e ".[dev,data,serve,api,db]"
pytest
```

The API tests run on in-memory SQLite. To run them against Postgres, set `WEEDLAB_TEST_DATABASE_URL`; the tests drop and recreate the tables in that database, so do not point it at data you want to keep. CI runs the tests and the migrations (up, down, up) against a real Postgres.

The frontend tests run with `npm test` and the checks with `npm run lint` and `npm run build`, all in the `frontend` folder. The API types come from `frontend/openapi.json`, and a test fails when that file no longer matches the API. After changing a route, save the running API's `/openapi.json` into that file and run `npm run gen-api`.

Training and evaluation need the extras `train` and `export` as well. The code is under `src/weedlab/`, run configs in `configs/`, database migrations in `migrations/`, and every number in the docs comes from files in `reports/`.

## Limitations

- Trained on close-up single-plant photos from one region and one growing season. It has not been tested on wide field views, drone images, other crops or other seasons.
- Most test images (685 of 845) come from one photo date, so the test scores mostly describe one session.
- Carpetweed is missed often even when clearly visible, and small weeds are missed far more than large ones.
- The rate limiter is in memory and per process, so it resets on restart and does not coordinate between workers. Behind a proxy it needs `WEEDLAB_TRUSTED_PROXY_HOPS` set to the right number, found by logging the header, or every visitor shares one counter. If the host changes its proxy layout, that number has to be checked again.
- Each detection is saved together with a JPEG copy of the photo, resized to at most 640 px on the long side (about 100 KB each). Photos are deleted after `WEEDLAB_RETENTION_DAYS` days (7 by default) or earlier with `DELETE /v1/detections/{id}`. The cleanup only runs while the service is running, so on a host that sleeps, expired photos stay until it wakes.
- There is no login. Visitors are separated by a random id kept in the browser (see [Privacy](#privacy)), which stops accidental viewing but is not strong access control, so do not expose the service publicly with photos you would not want others to see.
- The daily statistics group by UTC day, so a detection made late in the evening in the Americas can appear under the next day. They are computed in the application by reading all matching rows, which is fine for a demo but would need a database-side query for a large history.

## Documentation

- [`docs/architecture.md`](docs/architecture.md): how the pieces fit together and what happens on a detection
- [`docs/evaluation.md`](docs/evaluation.md): data split, results, error analysis and the experiments that did not work
- [`docs/model_card.md`](docs/model_card.md): intended use and failure modes
- [`docs/data_notes.md`](docs/data_notes.md): dataset audit, label fixes and the leakage check
- [`docs/runbook.md`](docs/runbook.md): deploying, rolling back and debugging
- [`docs/decisions/`](docs/decisions/): short records of why the main choices were made (split, model size, input size, threshold, ONNX, visitor ids, hosting, rate limiting)
- [`docs/product_brief.md`](docs/product_brief.md): who the demo is for and what it is meant to show

## Licensing

- Ultralytics YOLO is released under AGPL-3.0, which matters if anyone wants to run this as a commercial service.
- The dataset, CottonWeedDet12 (Dang et al., 2023), is listed as CC BY-NC 4.0 on its Hugging Face card, so models trained on it should be treated as non-commercial. Dataset record: https://zenodo.org/records/7535814.