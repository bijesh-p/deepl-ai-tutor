"""MCP server for document parsing.

Exposes tools for extracting text and images from PDF files.
Run standalone: PYTHONPATH=. uv run python -m mcp_servers.document_server.server
"""
from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("document_server")


@mcp.tool()
def extract_text_from_pdf(file_path: str, max_pages: int = 4) -> str:
    """Extract structured text from a PDF file.

    Returns JSON with title, sections, and metadata.
    """
    import fitz

    doc = fitz.open(file_path)
    pages_to_read = min(max_pages, len(doc))

    sections = []
    for page_num in range(pages_to_read):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:
            sections.append({
                "section_id": f"page-{page_num + 1}",
                "heading": f"Page {page_num + 1}",
                "body": text,
                "page_number": page_num + 1,
            })

    title = doc.metadata.get("title", "") or (
        sections[0]["body"].split("\n")[0][:100] if sections else "Untitled"
    )

    result = {
        "title": title,
        "total_pages": pages_to_read,
        "sections": sections,
    }
    doc.close()
    return json.dumps(result)


@mcp.tool()
def parse_images(file_path: str, max_pages: int = 4) -> str:
    """Extract images from a PDF and return metadata.

    Returns JSON list of image info (page, dimensions, index).
    """
    import fitz

    doc = fitz.open(file_path)
    pages_to_read = min(max_pages, len(doc))

    images = []
    for page_num in range(pages_to_read):
        page = doc[page_num]
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            images.append({
                "page": page_num + 1,
                "index": img_idx,
                "width": base_image.get("width", 0),
                "height": base_image.get("height", 0),
                "ext": base_image.get("ext", ""),
            })

    doc.close()
    return json.dumps(images)


if __name__ == "__main__":
    mcp.run()
