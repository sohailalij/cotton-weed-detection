"""Leakage-safe split: whole groups (photo sessions) go to exactly one split."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from weedlab.audit import parse_label_file

SPLITS = ("train", "val", "test")
N_CLASSES = 12


def group_of(stem: str, by: str = "date") -> str:
    parts = stem.split("_")
    if len(parts) < 4:
        return "unknown"
    return parts[0] if by == "date" else f"{parts[0]}_{parts[1]}"


def cost(
    totals: list[list[int]],
    grand: list[int],
    ratios: list[float],
    min_per_class: int,
) -> float:
    """Lower is better. Index 0 of each vector is the image count, then one slot per class."""
    total = 0.0
    for s, ratio in enumerate(ratios):
        for k, denom in enumerate(grand):
            if denom == 0:
                continue
            weight = 3.0 if k == 0 else 1.0
            total += weight * (totals[s][k] / denom - ratio) ** 2
        if s > 0:
            for k in range(1, len(grand)):
                if grand[k] > 0 and totals[s][k] < min_per_class:
                    total += 1.0 + (min_per_class - totals[s][k])
    return total


def _move(totals: list[list[int]], vec: list[int], a: int, b: int) -> None:
    for k, v in enumerate(vec):
        totals[a][k] -= v
        totals[b][k] += v


def assign_groups(
    vectors: list[list[int]],
    ratios: list[float],
    seed: int,
    restarts: int = 300,
    min_per_class: int = 8,
) -> tuple[list[int], float]:
    rng = random.Random(seed)
    n_groups = len(vectors)
    width = len(vectors[0])
    n_splits = len(ratios)
    grand = [sum(v[k] for v in vectors) for k in range(width)]
    best_assign: list[int] = []
    best_cost = float("inf")

    for _ in range(restarts):
        assign = [rng.randrange(n_splits) for _ in range(n_groups)]
        totals = [[0] * width for _ in range(n_splits)]
        for g, s in enumerate(assign):
            for k in range(width):
                totals[s][k] += vectors[g][k]
        current = cost(totals, grand, ratios, min_per_class)

        improved = True
        while improved:
            improved = False
            for g in rng.sample(range(n_groups), n_groups):
                src = assign[g]
                for dst in range(n_splits):
                    if dst == src:
                        continue
                    _move(totals, vectors[g], src, dst)
                    new = cost(totals, grand, ratios, min_per_class)
                    if new < current - 1e-12:
                        current = new
                        assign[g] = dst
                        src = dst
                        improved = True
                    else:
                        _move(totals, vectors[g], dst, src)

        if current < best_cost:
            best_cost = current
            best_assign = assign[:]

    return best_assign, best_cost


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=Path("data/processed/labels"))
    ap.add_argument("--out", type=Path, default=Path("configs/split_v1.json"))
    ap.add_argument("--group-by", choices=["date", "date_device"], default="date")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--restarts", type=int, default=300)
    ap.add_argument("--ratios", type=float, nargs=3, default=[0.70, 0.15, 0.15])
    args = ap.parse_args()

    ratios: list[float] = [r / sum(args.ratios) for r in args.ratios]
    groups: dict[str, list[str]] = defaultdict(list)
    image_classes: dict[str, set[int]] = {}
    for path in sorted(args.labels.glob("*.txt")):
        boxes, _ = parse_label_file(path)
        image_classes[path.stem] = {b[0] for b in boxes}
        groups[group_of(path.stem, args.group_by)].append(path.stem)

    names = sorted(groups)
    vectors: list[list[int]] = []
    for name in names:
        vec = [0] * (N_CLASSES + 1)
        for stem in groups[name]:
            vec[0] += 1
            for c in image_classes[stem]:
                vec[c + 1] += 1
        vectors.append(vec)

    biggest = sorted(((len(v), k) for k, v in groups.items()), reverse=True)[:3]
    print(f"{len(names)} groups, largest: {biggest}")

    assign, best = assign_groups(vectors, ratios, args.seed, args.restarts)
    print(f"final cost: {best:.4f}")
    if best >= 1.0:
        print("WARNING: some class has too few images in val or test")

    split_groups: dict[str, list[str]] = {s: [] for s in SPLITS}
    split_stems: dict[str, list[str]] = {s: [] for s in SPLITS}
    for name, idx in zip(names, assign, strict=True):
        split_groups[SPLITS[idx]].append(name)
        split_stems[SPLITS[idx]].extend(groups[name])

    seen: set[str] = set()
    for s in SPLITS:
        stems = set(split_stems[s])
        assert not (seen & stems), "an image appears in two splits"
        seen |= stems
    assert len(seen) == len(image_classes), "some images are unassigned"

    total = len(image_classes)
    for s in SPLITS:
        per_class: Counter[int] = Counter()
        for stem in split_stems[s]:
            for c in image_classes[stem]:
                per_class[c] += 1
        n = len(split_stems[s])
        print(f"\n{s}: {n} images ({n / total:.1%}), {len(split_groups[s])} groups")
        print("  images per class:", [per_class[c] for c in range(N_CLASSES)])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "group_by": args.group_by,
        "seed": args.seed,
        "ratios": ratios,
        "cost": best,
        "groups": {s: sorted(split_groups[s]) for s in SPLITS},
        "images": {s: sorted(split_stems[s]) for s in SPLITS},
    }
    args.out.write_text(json.dumps(manifest, indent=1))
    print(f"\nmanifest written to {args.out}")


if __name__ == "__main__":
    main()
