# Артефакт доков, не правило подбора.
# Pillow приходит из lock через reportlab (pillow==12.3.0); прямой зависимости в pyproject.toml нет.

"""График девяти канонических строк SYNTH-EVAL. SVG и PNG без matplotlib."""

from __future__ import annotations

from pathlib import Path

from product.matching.synth_eval import load_shards
from product.matching.synth_eval_run import collect_counts

_DOCS = Path(__file__).resolve().parent.parent / "docs"
_FONT = Path(__file__).resolve().parent.parent / "static" / "fonts" / "JetBrainsMono-Regular.ttf"

_WIDTH = 880
_ROW = 46
_TOP = 36
_LABEL_X = 16
_BAR_X = 300
_BAR_MAX = 400
_BAR_H = 12
_HIT_FILL = "#2f6f9f"
_TOTAL_FILL = "#c8d7e4"
_HIT_RGB = (47, 111, 159)
_TOTAL_RGB = (200, 215, 228)


def _geometry(counts: dict[str, tuple[int, int]]) -> tuple[int, int, int]:
    height = _TOP + _ROW * len(counts) + 20
    max_total = max((total for _hit, total in counts.values()), default=1) or 1
    return _WIDTH, height, max_total


def _svg(counts: dict[str, tuple[int, int]]) -> str:
    width, height, max_total = _geometry(counts)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, (name, (hit, total)) in enumerate(counts.items()):
        y = _TOP + index * _ROW
        label = f"{name} {hit} {total}"
        hit_w = int(_BAR_MAX * hit / max_total)
        total_w = int(_BAR_MAX * total / max_total)
        parts.append(
            f'<text x="{_LABEL_X}" y="{y}" font-size="14" font-family="monospace">{label}</text>'
        )
        parts.append(
            f'<rect x="{_BAR_X}" y="{y - 12}" width="{hit_w}" height="{_BAR_H}" fill="{_HIT_FILL}"/>'
        )
        parts.append(
            f'<rect x="{_BAR_X + hit_w + 8}" y="{y - 12}" width="{total_w}" height="{_BAR_H}" fill="{_TOTAL_FILL}"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _png(counts: dict[str, tuple[int, int]], path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height, max_total = _geometry(counts)
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(_FONT), 14)
    for index, (name, (hit, total)) in enumerate(counts.items()):
        y = _TOP + index * _ROW
        label = f"{name} {hit} {total}"
        hit_w = int(_BAR_MAX * hit / max_total)
        total_w = int(_BAR_MAX * total / max_total)
        draw.text((_LABEL_X, y - 16), label, fill=(32, 32, 32), font=font)
        draw.rectangle(
            [_BAR_X, y - 12, _BAR_X + hit_w, y - 12 + _BAR_H],
            fill=_HIT_RGB,
        )
        total_left = _BAR_X + hit_w + 8
        draw.rectangle(
            [total_left, y - 12, total_left + total_w, y - 12 + _BAR_H],
            fill=_TOTAL_RGB,
        )
    image.save(path, format="PNG")


def write_chart(directory: Path, bundle: dict | None = None) -> tuple[Path, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    counts = collect_counts(bundle)
    svg_path = directory / "synth_eval.svg"
    png_path = directory / "synth_eval.png"
    svg_path.write_text(_svg(counts), encoding="utf-8")
    _png(counts, png_path)
    return svg_path, png_path


def main() -> None:
    bundle = load_shards()
    if len(bundle.get("shards") or []) != 4 or bundle.get("n") != 1000:
        raise SystemExit("shards_incomplete")
    write_chart(_DOCS, bundle)


if __name__ == "__main__":
    main()
