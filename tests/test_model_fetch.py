import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from weedlab.api.model_fetch import ModelFetchError, ensure_model

DATA = b"pretend these are onnx bytes"
HASH = hashlib.sha256(DATA).hexdigest()
URL = "https://example.com/model.onnx"


def fake_download(url: str) -> Iterator[bytes]:
    yield DATA[:7]
    yield DATA[7:]


def must_not_download(url: str) -> Iterator[bytes]:
    raise AssertionError("should not download")
    yield b""


def test_present_file_is_left_alone_without_a_hash(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"anything")
    assert ensure_model(model, None, None, must_not_download) == "present"


def test_present_file_with_matching_hash_is_kept(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(DATA)
    assert ensure_model(model, URL, HASH, must_not_download) == "present"


def test_missing_file_is_downloaded_and_verified(tmp_path: Path) -> None:
    model = tmp_path / "sub" / "m.onnx"
    assert ensure_model(model, URL, HASH, fake_download) == "downloaded"
    assert model.read_bytes() == DATA
    assert list(model.parent.glob("*.part")) == []


def test_uppercase_hash_is_accepted(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    assert ensure_model(model, URL, HASH.upper(), fake_download) == "downloaded"


def test_wrong_hash_is_refused_and_nothing_is_left_behind(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    with pytest.raises(ModelFetchError, match="does not match"):
        ensure_model(model, URL, "0" * 64, fake_download)
    assert not model.exists()
    assert list(tmp_path.glob("*.part")) == []


def test_file_with_the_wrong_hash_is_replaced_when_a_url_is_given(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"old model")
    assert ensure_model(model, URL, HASH, fake_download) == "downloaded"
    assert model.read_bytes() == DATA


def test_file_with_the_wrong_hash_and_no_url_is_an_error(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"old model")
    with pytest.raises(ModelFetchError, match="no URL"):
        ensure_model(model, None, HASH, must_not_download)


def test_missing_file_without_a_url_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ModelFetchError, match="WEEDLAB_MODEL_URL"):
        ensure_model(tmp_path / "m.onnx", None, None, must_not_download)


def test_download_requires_a_hash(tmp_path: Path) -> None:
    with pytest.raises(ModelFetchError, match="SHA256 is required"):
        ensure_model(tmp_path / "m.onnx", URL, None, must_not_download)


def test_only_https_urls_are_accepted(tmp_path: Path) -> None:
    with pytest.raises(ModelFetchError, match="https"):
        ensure_model(tmp_path / "m.onnx", "http://example.com/m.onnx", HASH, must_not_download)
