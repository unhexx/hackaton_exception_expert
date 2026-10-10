"""Прогон SYNTH-EVAL. Печатает девять канонических строк записки."""

from __future__ import annotations

import sys

from product.matching.synth_eval import load_shards, render_synth_report


def main() -> None:
    bundle = load_shards()
    if len(bundle.get("shards") or []) != 4 or bundle.get("n") != 1000:
        raise SystemExit("shards_incomplete")
    sys.stdout.write(render_synth_report(bundle))


if __name__ == "__main__":
    main()
