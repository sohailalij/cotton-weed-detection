"""Make sure the ONNX model file is on disk before the API starts.

Run as ``python -m weedlab.api.model_fetch``. Settings come from the environment:

- WEEDLAB_MODEL_PATH: where the API expects the model (required)
- WEEDLAB_MODEL_URL: https address to download it from if it is missing
- WEEDLAB_MODEL_SHA256: expected SHA-256 of the file (required when downloading)
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

CHUNK = 1024 * 1024


class ModelFetchError(RuntimeError):
    """The model file is missing or is not the file that was expected."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str) -> Iterator[bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "weedlab-model-fetch"})
    with urllib.request.urlopen(request, timeout=60) as response:
        while chunk := response.read(CHUNK):
            yield chunk


def ensure_model(
    path: Path,
    url: str | None,
    sha256: str | None,
    download: Callable[[str], Iterator[bytes]] = _download,
) -> str:
    """Return "present" or "downloaded", or raise ModelFetchError."""
    expected = sha256.strip().lower() if sha256 else None

    if path.is_file():
        if expected is None or sha256_of(path) == expected:
            return "present"
        if not url:
            raise ModelFetchError(
                f"{path} does not match WEEDLAB_MODEL_SHA256 and there is no URL to replace it"
            )

    if not url:
        raise ModelFetchError(f"model file {path} is missing and WEEDLAB_MODEL_URL is not set")
    if not url.startswith("https://"):
        raise ModelFetchError("WEEDLAB_MODEL_URL must start with https://")
    if expected is None:
        raise ModelFetchError("WEEDLAB_MODEL_SHA256 is required when the model is downloaded")

    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    handle, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".part")
    temp = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as out:
            for chunk in download(url):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != expected:
            raise ModelFetchError(
                "the downloaded model does not match WEEDLAB_MODEL_SHA256; refusing to use it"
            )
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return "downloaded"


def main() -> int:
    raw_path = os.environ.get("WEEDLAB_MODEL_PATH")
    if not raw_path:
        print("model check failed: WEEDLAB_MODEL_PATH is not set", file=sys.stderr)
        return 1
    try:
        outcome = ensure_model(
            Path(raw_path),
            os.environ.get("WEEDLAB_MODEL_URL") or None,
            os.environ.get("WEEDLAB_MODEL_SHA256") or None,
        )
    except (ModelFetchError, OSError) as error:
        print(f"model check failed: {error}", file=sys.stderr)
        return 1
    print(f"model {outcome}: {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
