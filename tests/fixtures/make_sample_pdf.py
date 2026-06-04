"""Run once to generate tests/fixtures/sample.pdf used in test_pdf_parser."""
import fitz
from pathlib import Path

out = Path(__file__).parent / "sample.pdf"
doc = fitz.open()

pages = [
    ("Introduction to Machine Learning", "Machine learning is a subset of AI that enables systems to learn from data."),
    ("Supervised Learning", "Supervised learning uses labelled training data to learn a mapping from inputs to outputs."),
    ("Unsupervised Learning", "Unsupervised learning finds hidden patterns in data without labelled responses."),
]

for title, body in pages:
    page = doc.new_page()
    page.insert_text((50, 72), title, fontsize=18)
    page.insert_text((50, 120), body, fontsize=12)

doc.set_toc([
    [1, "Introduction to Machine Learning", 1],
    [1, "Supervised Learning", 2],
    [1, "Unsupervised Learning", 3],
])
doc.set_metadata({"title": "Sample ML Document"})
doc.save(str(out))
print(f"Saved {out}")
