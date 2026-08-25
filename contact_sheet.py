"""Contact-sheet rendering for model-friendly photo comparison."""

from __future__ import annotations

from io import BytesIO
from math import ceil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


BACKGROUND = "#151515"
CELL_BACKGROUND = "#242424"
TEXT = "#f5f5f5"
MUTED_TEXT = "#b7b7b7"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10 compatibility
        return ImageFont.load_default()


def render_contact_sheet(
    query: str,
    results: list[dict[str, Any]],
    columns: int = 5,
    thumbnail_width: int = 256,
    thumbnail_height: int = 192,
) -> bytes:
    """Render labeled results into a single PNG and return its bytes."""
    if not results:
        raise ValueError("Cannot create a contact sheet without results")
    if not 1 <= columns <= 10:
        raise ValueError("columns must be between 1 and 10")

    gap = 12
    outer = 20
    cell_width = thumbnail_width
    cell_height = thumbnail_height
    rows = ceil(len(results) / columns)
    width = outer * 2 + columns * cell_width + (columns - 1) * gap
    height = outer * 2 + rows * cell_height + (rows - 1) * gap

    sheet = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    body_font = _font(15)

    for position, result in enumerate(results):
        row, column = divmod(position, columns)
        x = outer + column * (cell_width + gap)
        y = outer + row * (cell_height + gap)
        draw.rounded_rectangle(
            (x, y, x + cell_width, y + cell_height),
            radius=8,
            fill=CELL_BACKGROUND,
        )

        image_box = (x, y, x + thumbnail_width, y + thumbnail_height)
        path = Path(result["path"])
        try:
            with Image.open(path) as source:
                source = ImageOps.exif_transpose(source).convert("RGB")
                fitted = ImageOps.contain(source, (thumbnail_width, thumbnail_height))
                paste_x = x + (thumbnail_width - fitted.width) // 2
                paste_y = y + (thumbnail_height - fitted.height) // 2
                sheet.paste(fitted, (paste_x, paste_y))
        except Exception:
            draw.rectangle(image_box, fill="#333333")
            draw.text((x + 16, y + 78), "unavailable", font=body_font, fill=MUTED_TEXT)

    output = BytesIO()
    sheet.save(output, format="PNG", optimize=True)
    return output.getvalue()


def make_manifest(search_result: dict[str, Any], columns: int = 5) -> dict[str, Any]:
    """Create the machine-readable grid-position mapping paired with a sheet."""
    items = []
    for position, result in enumerate(search_result["results"], start=1):
        items.append(
            {
                "position": position,
                "row": ((position - 1) // columns) + 1,
                "column": ((position - 1) % columns) + 1,
                "photo_id": result["photo_id"],
                "rank": result["rank"],
                "score": result["score"],
                "filename": result["filename"],
                "parent_dir": result["parent_dir"],
                "path": result["path"],
                "available": result["exists"],
            }
        )
    return {
        "query": search_result["query"],
        "count": len(items),
        "grid": {
            "columns": columns,
            "rows": ceil(len(items) / columns),
            "order": "left-to-right, then top-to-bottom",
        },
        "total_indexed": search_result["total_indexed"],
        "execution_time_ms": search_result["execution_time_ms"],
        "instructions": (
            "Choose images by grid position (1-based row and column), then call get_photo "
            "with the corresponding photo_id."
        ),
        "items": items,
    }
