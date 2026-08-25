#!/usr/bin/env python3
"""Read-only MCP server for agent-native photo search and contact sheets."""

from __future__ import annotations

import json
import logging
import sys
from io import BytesIO
from typing import Annotated

from mcp.server.mcpserver import Image, MCPServer
from mcp_types import TextContent
from PIL import Image as PILImage
from PIL import ImageOps
from pydantic import Field

from contact_sheet import make_manifest, render_contact_sheet
from photo_search_engine import engine


logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[photo-search-mcp] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

server = MCPServer(
    name="photo-search",
    title="Photo Search Contact Sheets",
    description="Search a local photo library and compare ranked results in labeled contact sheets.",
    instructions=(
        "Use search_photo_contact_sheet to visually inspect 10-50 ranked photos at once. "
        "The sheet is a five-column grid ordered left-to-right, then top-to-bottom; map a "
        "chosen row and column to photo_id using the JSON manifest. Use get_photo only for "
        "shortlisted IDs that need closer inspection. This server is read-only."
    ),
    version="0.1.0",
)


@server.tool(structured_output=False)
def search_photo_contact_sheet(
    query: Annotated[str, Field(min_length=1, description="Natural-language description of the desired photos")],
    count: Annotated[int, Field(ge=10, le=50, description="Number of results to place on the sheet")] = 25,
    threshold: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Optional minimum raw similarity score"),
    ] = 0.0,
) -> list[TextContent | Image]:
    """Search photos and return one compact five-column contact sheet plus its JSON manifest."""
    result = engine.search(query=query, count=count, threshold=threshold)
    if not result["results"]:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "query": query,
                        "count": 0,
                        "message": "No photos met the requested threshold.",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    sheet = render_contact_sheet(query=query, results=result["results"])
    manifest = make_manifest(result)
    return [
        TextContent(type="text", text=json.dumps(manifest, ensure_ascii=False, indent=2)),
        Image(data=sheet, format="png"),
    ]


@server.tool(structured_output=False)
def get_photo(
    photo_id: Annotated[str, Field(pattern=r"^photo_[0-9a-f]{16}$")],
    max_edge: Annotated[
        int,
        Field(ge=512, le=4096, description="Maximum preview width or height in pixels"),
    ] = 1600,
) -> list[TextContent | Image]:
    """Return a larger preview for one photo_id selected from a contact sheet."""
    metadata = engine.get_photo(photo_id)
    with PILImage.open(metadata["path"]) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        source.thumbnail((max_edge, max_edge), PILImage.Resampling.LANCZOS)
        output = BytesIO()
        source.save(output, format="JPEG", quality=88, optimize=True)

    text_metadata = {**metadata, "preview_max_edge": max_edge}
    return [
        TextContent(type="text", text=json.dumps(text_metadata, ensure_ascii=False, indent=2)),
        Image(data=output.getvalue(), format="jpeg"),
    ]


@server.tool()
def photo_search_stats() -> dict[str, object]:
    """Report index size, model, device, and readiness."""
    engine.load()
    return engine.stats()


if __name__ == "__main__":
    server.run(transport="stdio")
