"""Rebuild labels and the split from raw data, then check against the committed manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", module, *args]
    print("->", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("configs/split_v1.json"))
    ap.add_argument("--rebuilt", type=Path, default=Path("data/processed/split_rebuilt.json"))
    args = ap.parse_args()

    run("weedlab.convert_labels", "--root", str(args.root))
    run("weedlab.split", "--out", str(args.rebuilt))

    committed = json.loads(args.manifest.read_text())
    rebuilt = json.loads(args.rebuilt.read_text())
    if all(committed[k] == rebuilt[k] for k in ("groups", "images")):
        print("\nOK: rebuilt split matches the committed manifest")
    else:
        print("\nMISMATCH: rebuilt split differs from the committed manifest")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
