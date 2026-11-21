"""Turns a file into text and images for the document reader.

Rules are in docs/import-und-routen.md §5. A PDF with text goes through
pdftotext. A PDF without text is a scan and goes to the vision model.
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
_MAX_SCAN_PAGES = 3


class ContentError(Exception):
    """A file cannot be turned into text or images."""


def extract(path: str, data: bytes) -> tuple[str, list[tuple[bytes, str]]]:
    """Returns the text of a file and its images for the vision model."""
    suffix = pathlib.PurePosixPath(path).suffix.lower()
    if suffix in _IMAGE_TYPES:
        return "", [(data, _IMAGE_TYPES[suffix])]
    if suffix == ".pdf":
        text = _pdf_text(data)
        if len(text.strip()) >= _MIN_PDF_TEXT_CHARS:
            return text[:MAX_TEXT_CHARS], []
        return "", _pdf_pages(data)
    if suffix == ".docx":
        return _docx_text(data)[:MAX_TEXT_CHARS], []
    if suffix in (".xlsx", ".xls"):
        return _xlsx_text(data)[:MAX_TEXT_CHARS], []
    if suffix == ".json":
        try:
            text = json.dumps(json.loads(tables.decode(data)), indent=1, ensure_ascii=False)
        except json.JSONDecodeError:
            text = tables.decode(data)
        return text[:MAX_TEXT_CHARS], []
    if suffix in (".txt", ".md", ".csv", ".eml", ""):
        return tables.decode(data)[:MAX_TEXT_CHARS], []
    raise ContentError(f"File type '{suffix}' is not supported")


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


def _pdf_pages(data: bytes) -> list[tuple[bytes, str]]:
    with tempfile.TemporaryDirectory() as folder:
        source = pathlib.Path(folder) / "scan.pdf"
        source.write_bytes(data)
        _run(["pdftoppm", "-png", "-r", "110", "-l", str(_MAX_SCAN_PAGES),
              str(source), str(pathlib.Path(folder) / "page")])
        pages = sorted(pathlib.Path(folder).glob("page*.png"))
        return [(page.read_bytes(), "image/png") for page in pages]


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
