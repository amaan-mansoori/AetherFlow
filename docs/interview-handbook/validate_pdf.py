#!/usr/bin/env python3
"""Validate handbook PDF structure, extracted content, page text, and links."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "docs" / "AetherFlow_Technical_Interview_Handbook.pdf"
CHAPTERS = [
    "Chapter 1 — Executive Overview",
    "Chapter 2 — Problem Statement and Design Goals",
    "Chapter 3 — Complete System Architecture",
    "Chapter 4 — End-to-End Job Lifecycle",
    "Chapter 5 — Transactional Outbox Deep Dive",
    "Chapter 6 — Kafka and Asynchronous Processing",
    "Chapter 7 — PostgreSQL and Data Consistency",
    "Chapter 8 — Worker Reliability, Leases and Retries",
    "Chapter 9 — Scheduling",
    "Chapter 10 — AI Provider Integration",
    "Chapter 11 — FastAPI and API Design",
    "Chapter 12 — Frontend and User Experience",
    "Chapter 13 — Authentication and Security",
    "Chapter 14 — Observability and Operations",
    "Chapter 15 — Testing and Quality Engineering",
    "Chapter 16 — Technology Choices and Alternatives",
    "Chapter 17 — Engineering Challenges and Trade-Offs",
    "Chapter 18 — Scalability and Performance",
    "Chapter 19 — Deployment Decision and Honest Limitations",
    "Chapter 20 — Interview Question Bank with Answers",
    "Chapter 21 — Mock Interviews",
    "Chapter 22 — Source-Code Navigation Guide",
    "Chapter 23 — Glossary and Final Revision Sheets",
]


def validate(path: Path, render_pages: list[int], render_dir: Path | None) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"handbook PDF does not exist: {path}")
    if path.stat().st_size < 20_000:
        raise ValueError(f"PDF is unexpectedly small: {path.stat().st_size} bytes")
    with path.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            raise ValueError("file does not begin with a PDF signature")
    reader = PdfReader(path, strict=True)
    if len(reader.pages) < 20:
        raise ValueError(f"unexpectedly few PDF pages: {len(reader.pages)}")

    page_text: list[str] = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if len(text.strip()) < 10:
            raise ValueError(f"page {number} appears blank or text extraction failed")
        if "\ufffd" in text or "\u25a1" in text:
            raise ValueError(f"page {number} contains a replacement/missing glyph")
        page_text.append(text)
    all_text = "\n".join(page_text)
    missing = [chapter for chapter in CHAPTERS if chapter not in all_text]
    if missing:
        raise ValueError(f"chapter headings missing from extracted PDF text: {missing}")
    for required in (
        "Contents",
        "30-second",
        "PostgreSQL",
        "transactional outbox",
        "Top 25 questions",
        "Source-verification note",
    ):
        if required.casefold() not in all_text.casefold():
            raise ValueError(f"required extracted text was not found: {required}")

    links = 0
    internal_links = 0
    invalid_file_links: list[str] = []
    for page in reader.pages:
        for annotation in page.get("/Annots", []):
            data = annotation.get_object()
            if data.get("/Subtype") != "/Link":
                continue
            links += 1
            action = data.get("/A", {})
            uri = str(action.get("/URI", "")) if action else ""
            destination = data.get("/Dest")
            if destination is not None or uri.startswith("#"):
                internal_links += 1
            parsed = urlparse(uri)
            if parsed.scheme == "file":
                local_path = Path(unquote(parsed.path).lstrip("/"))
                if re.match(r"^/[A-Za-z]:", unquote(parsed.path)):
                    local_path = Path(unquote(parsed.path)[1:].replace("/", "\\"))
                if not local_path.exists():
                    invalid_file_links.append(uri)
    if internal_links < 20:
        raise ValueError(f"table-of-contents links appear incomplete: {internal_links}")
    if invalid_file_links:
        raise ValueError(f"broken local PDF links: {invalid_file_links[:10]}")

    print(f"PDF: {path}")
    print(f"Size: {path.stat().st_size:,} bytes")
    print(f"Pages: {len(reader.pages)}; text extracted from all pages")
    print(f"Chapter headings: {len(CHAPTERS)}/23 found")
    print(f"Links: {links} total, {internal_links} internal")
    print("Blank pages/missing-glyph markers: none detected")
    for index in (0, 1, min(2, len(page_text) - 1), len(page_text) - 1):
        tail = [line.strip() for line in page_text[index].splitlines() if line.strip()][-3:]
        print(f"Page {index + 1} ending text: {' | '.join(tail)}")
    if render_pages:
        if render_dir is None:
            raise ValueError("--render-dir is required when --render-pages is specified")
        try:
            import pymupdf
        except ImportError as error:
            raise RuntimeError(
                "Install optional validators with "
                "python -m pip install -r docs/interview-handbook/requirements-validation.txt"
            ) from error
        if not render_dir.exists():
            render_dir.mkdir(parents=True)
        document = pymupdf.open(path)
        for page_number in render_pages:
            if not 1 <= page_number <= len(document):
                raise ValueError(f"render page is outside the PDF: {page_number}")
            image = render_dir / f"aetherflow-handbook-page-{page_number:02}.png"
            pixmap = document[page_number - 1].get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5),
                alpha=False,
            )
            pixmap.save(image)
            print(f"Rendered page {page_number}: {image}")
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=PDF_PATH)
    parser.add_argument(
        "--render-pages",
        default="",
        help="comma-separated one-based page numbers to rasterize for visual review",
    )
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    selected_pages = [
        int(value)
        for value in args.render_pages.split(",")
        if value.strip()
    ]
    validate(
        args.pdf.resolve(),
        selected_pages,
        args.render_dir.resolve() if args.render_dir else None,
    )


if __name__ == "__main__":
    main()
