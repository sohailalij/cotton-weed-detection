"""Look for near-duplicate images, especially pairs that sit in different splits."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image

HASH_SIZE = 8


def dhash(path: Path) -> int:
    """64-bit difference hash: does each pixel brighten from left to right?"""
    with Image.open(path) as im:
        im.draft("L", (128, 128))
        small = im.convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.Resampling.LANCZOS)
        px = small.tobytes()
    bits = 0
    for row in range(HASH_SIZE):
        for col in range(HASH_SIZE):
            i = row * (HASH_SIZE + 1) + col
            bits = (bits << 1) | int(px[i] > px[i + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("configs/split_v1.json"))
    ap.add_argument("--out", type=Path, default=Path("reports/near_duplicates.csv"))
    ap.add_argument("--threshold", type=int, default=6)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    split_of: dict[str, str] = {}
    for split, stems in manifest["images"].items():
        for stem in stems:
            split_of[stem] = split

    img_dir: Path = args.root / "weedImages"
    images = {p.stem: p for p in img_dir.iterdir()}
    stems = sorted(split_of)
    hashes: list[int] = []
    for n, stem in enumerate(stems, start=1):
        hashes.append(dhash(images[stem]))
        if n % 500 == 0:
            print(f"  hashed {n}/{len(stems)}", flush=True)

    print("comparing all pairs...", flush=True)
    pairs: list[tuple[int, str, str]] = []
    for i, hi in enumerate(hashes):
        for j in range(i + 1, len(hashes)):
            d = hamming(hi, hashes[j])
            if d <= args.threshold:
                pairs.append((d, stems[i], stems[j]))
    pairs.sort()

    counts = {"same_split_same_date": 0, "same_split_diff_date": 0}
    counts |= {"cross_split_same_date": 0, "cross_split_diff_date": 0}
    cross: list[tuple[int, str, str]] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["distance", "image_a", "image_b", "split_a", "split_b", "same_date"])
        for d, a, b in pairs:
            same_date = a.split("_")[0] == b.split("_")[0]
            same_split = split_of[a] == split_of[b]
            key = ("same_split" if same_split else "cross_split") + (
                "_same_date" if same_date else "_diff_date"
            )
            counts[key] += 1
            if not same_split:
                cross.append((d, a, b))
            w.writerow([d, a, b, split_of[a], split_of[b], same_date])

    print(f"\nnear-duplicate pairs (distance <= {args.threshold}): {len(pairs)}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"\nclosest cross-split pairs (showing up to 15 of {len(cross)}):")
    for d, a, b in cross[:15]:
        print(f"  d={d}  {a} ({split_of[a]})  <->  {b} ({split_of[b]})")
    print(f"\nreport written to {args.out}")


if __name__ == "__main__":
    main()
