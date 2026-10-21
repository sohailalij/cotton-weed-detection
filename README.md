# Cotton weed detection

Upload a close-up photo of a cotton field and get back bounding boxes, species labels and a weed coverage estimate for 12 weed species. A YOLO11s detector trained on CottonWeedDet12, served through a FastAPI service with ONNX Runtime on CPU, with detection history stored in Postgres.

**Status:** data pipeline, training, evaluation and the API are done. The web frontend and public deployment are not built yet.

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

Then start the API and the database:

```
docker compose up --build
```

The service listens on `http://localhost:8000`, applies the database migrations on startup, and serves interactive docs at `/docs`. Try it:

```
curl -F "file=@photo.jpg" "http://localhost:8000/v1/detect?conf=0.58"
```

| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/detect` | Upload an image; returns boxes, species, scores and box coverage, and saves the result |
| GET | `/v1/detections` | Paginated history, newest first |
| GET | `/v1/detections/{id}` | One saved result |
| GET | `/v1/stats` | Species counts and mean coverage, optionally between `start` and `end` |
| GET | `/v1/model` | Model name, input size, classes and test metrics |
| GET | `/health` | Liveness |

Uploads are limited to JPEG, PNG and WEBP, decoded rather than trusted by header, 15 MB and 50 million pixels by default. `/v1/detect` is rate limited per client.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `WEEDLAB_MODEL_PATH` | required | Path to the ONNX model |
| `WEEDLAB_DATABASE_URL` | required | SQLAlchemy URL, for example `postgresql+psycopg://user:pass@host:5432/db` |
| `WEEDLAB_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins; `*` is refused |
| `WEEDLAB_MAX_UPLOAD_MB` | `15` | Upload size limit |
| `WEEDLAB_RATE_LIMIT_PER_MINUTE` | `10` | Requests per client per minute on `/v1/detect` |

The service refuses to start if a required setting is missing or a value is invalid. The credentials in `docker-compose.yml` are for local development only.

## Develop

```
pip install -e ".[dev,data,serve,api,db]"
pytest
```

The API tests run on in-memory SQLite. To run them against Postgres, set `WEEDLAB_TEST_DATABASE_URL`; the tests drop and recreate the tables in that database, so do not point it at data you want to keep. CI runs the tests and the migrations (up, down, up) against a real Postgres.

Training and evaluation need the extras `train` and `export` as well. The code is under `src/weedlab/`, run configs in `configs/`, database migrations in `migrations/`, and every number in the docs comes from files in `reports/`.

## Limitations

- Trained on close-up single-plant photos from one region and one growing season. It has not been tested on wide field views, drone images, other crops or other seasons.
- Most test images (685 of 845) come from one photo date, so the test scores mostly describe one session.
- Carpetweed is missed often even when clearly visible, and small weeds are missed far more than large ones.
- The rate limiter is in memory and per process, so it resets on restart and does not coordinate between workers. It keys on the client address the app sees, so behind a proxy or Docker Desktop every client can share one counter unless forwarded addresses are configured.
- Only metadata is stored for each detection, not the image.

## Licensing

- Ultralytics YOLO is released under AGPL-3.0, which matters if anyone wants to run this as a commercial service.
- The dataset, CottonWeedDet12 (Dang et al., 2023), is listed as CC BY-NC 4.0 on its Hugging Face card, so models trained on it should be treated as non-commercial. Dataset record: https://zenodo.org/records/7535814.