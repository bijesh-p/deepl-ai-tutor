"""MCP server for document parsing.

Exposes tools for extracting text and images from PDF files.
Run standalone: PYTHONPATH=. uv run python -m mcp_servers.document_server.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("document_server")


@mcp.tool()
def extract_text_from_pdf(file_path: str, max_pages: int = 4) -> str:
    """Extract structured text from a PDF file.

    Returns the JSON-encoded `Document` model (see backend.ingestion.models),
    i.e. the same shape produced by `backend.ingestion.pdf_parser.parse_pdf`.
    """
    from backend.ingestion.pdf_parser import parse_pdf

    doc = parse_pdf(file_path, max_pages=max_pages)
    return doc.to_json()


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
