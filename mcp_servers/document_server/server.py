"""MCP server for document parsing.

Exposes tools for extracting text and images from PDF files.
Run standalone: PYTHONPATH=. uv run python -m mcp_servers.document_server.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("document_server")


@mcp.tool()
def extract_text_from_pdf(file_path: str, max_pages: int = 10) -> str:
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


@mcp.tool()
def extract_text_from_pptx(file_path: str, max_slides: int = 16) -> str:
    """Extract structured text from a PowerPoint file.

    Returns the JSON-encoded `Document` model (see backend.ingestion.models).
    Each slide becomes a Section; slides with no body text are skipped.
    """
    from backend.ingestion.pptx_parser import parse_pptx

    doc = parse_pptx(file_path, max_slides=max_slides)
    return doc.to_json()


@mcp.tool()
def extract_text_from_docx(file_path: str, max_sections: int = 16) -> str:
    """Extract structured text from a Word document.

    Returns the JSON-encoded `Document` model (see backend.ingestion.models).
    Sections are derived from heading paragraphs.
    """
    from backend.ingestion.docx_parser import parse_docx

    doc = parse_docx(file_path, max_sections=max_sections)
    return doc.to_json()


@mcp.tool()
def extract_text_from_vtt(file_path: str, max_sections: int = 16) -> str:
    """Extract structured text from a WebVTT transcript file.

    Returns the JSON-encoded `Document` model (see backend.ingestion.models).
    Strips speaker names, filters chatter, and captures Q&A exchanges.
    """
    from backend.ingestion.vtt_parser import parse_vtt

    doc = parse_vtt(file_path, max_sections=max_sections)
    return doc.to_json()


if __name__ == "__main__":
    mcp.run()
