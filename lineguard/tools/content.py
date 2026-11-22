"""Turns a file into text and images for the document reader.

Rules are in docs/import-und-routen.md §5. Each PDF page with little text
goes to the vision model.
"""

import io
import json
import pathlib
import subprocess
import tempfile

import docx
import openpyxl

from lineguard.agents.reader import tables

MAX_TEXT_CHARS = 14000
_MIN_PDF_TEXT_CHARS = 50
_IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class ContentError(Exception):
    """A file cannot be turned into text or images."""


def extract_parts(path: str, data: bytes) -> list[tuple[str, str, list[tuple[bytes, str]]]]:
    """Returns text and images with a location for each part of a file."""
    suffix = pathlib.PurePosixPath(path).suffix.lower()
    if suffix in _IMAGE_TYPES:
        return [("image", "", [(data, _IMAGE_TYPES[suffix])])]
    if suffix == ".pdf":
        text = _pdf_text(data)
        pages = text.split("\f")
        if pages[-1] == "":
            pages.pop()
        if not pages:
            raise ContentError("PDF contains no pages")
        scanned = [index for index, page in enumerate(pages, 1)
                   if len(page.strip()) < _MIN_PDF_TEXT_CHARS]
        images = dict(zip(scanned, _pdf_pages(data, scanned), strict=True))
        return [(f"page {number}", "" if number in images else page,
                 [images[number]] if number in images else [])
                for number, page in enumerate(pages, 1)]
    if suffix == ".docx":
        text = _docx_text(data)
    elif suffix in (".xlsx", ".xls"):
        text = _xlsx_text(data)
    elif suffix == ".json":
        try:
            text = json.dumps(json.loads(tables.decode(data)), indent=1, ensure_ascii=False)
        except json.JSONDecodeError:
            text = tables.decode(data)
    elif suffix in (".txt", ".md", ".csv", ".eml", ""):
        text = tables.decode(data)
    else:
        raise ContentError(f"File type '{suffix}' is not supported")
    return [("document", text, [])]


def extract(path: str, data: bytes) -> tuple[str, list[tuple[bytes, str]]]:
    """Returns all text and images of a file."""
    parts = extract_parts(path, data)
    return "\n".join(text for _, text, _ in parts), [
        image for _, _, images in parts for image in images]


def _run(command: list[str], data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(command, input=data, capture_output=True,
                                check=True, timeout=60)
    except FileNotFoundError as error:
        raise ContentError(f"Program '{command[0]}' is not installed") from error
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ContentError(f"'{command[0]}' failed: {error}") from error
    return result.stdout


def _pdf_text(data: bytes) -> str:
    return _run(["pdftotext", "-layout", "-", "-"], data).decode("utf-8", "replace")


def _pdf_pages(data: bytes, page_numbers: list[int]) -> list[tuple[bytes, str]]:
    if not page_numbers:
        return []
    with tempfile.TemporaryDirectory() as folder:
        source = pathlib.Path(folder) / "scan.pdf"
        source.write_bytes(data)
        pages = []
        for number in page_numbers:
            target = pathlib.Path(folder) / f"page-{number}"
            _run(["pdftoppm", "-png", "-r", "110", "-f", str(number),
                  "-l", str(number), "-singlefile", str(source), str(target)])
            pages.append((target.with_suffix(".png").read_bytes(), "image/png"))
        return pages


def _docx_text(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def _xlsx_text(data: bytes) -> str:
    workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    lines = []
    for sheet in workbook.worksheets:
        lines.append(f"Sheet {sheet.title}:")
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                lines.append(";".join("" if c is None else str(c) for c in row))
    workbook.close()
    return "\n".join(lines)
