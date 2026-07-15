"""Document upload: extract plain text from PDF, DOCX, or plain-text files."""
import asyncio
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from auth import current_user
from rate_limit import burst_limit
from fastapi import Request

router = APIRouter(prefix="/api", tags=["upload"])

MAX_FILE_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_TEXT_CHARS = 8_000              # truncate extracted text to this length

ACCEPTED_TYPES = {
    ".txt", ".md", ".csv", ".json", ".log",  # plain text
    ".pdf",                                   # PDF
    ".docx",                                  # Word
}


def _extract_text_pdf(data: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(
            status_code=415,
            detail="PDF parsing requires pdfplumber. Run: pip install pdfplumber",
        )
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text_parts.append(text)
            if sum(len(p) for p in text_parts) >= MAX_TEXT_CHARS:
                break
    return "\n\n".join(text_parts)


def _extract_text_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(
            status_code=415,
            detail="Word document parsing requires python-docx. Run: pip install python-docx",
        )
    doc = Document(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_text_plain(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode("latin-1", errors="replace")


def _suffix(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""


@router.post("/parse-document")
@burst_limit("20/minute")
async def parse_document(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> JSONResponse:
    """Extract plain text from an uploaded document. Returns up to 8000 chars."""
    filename = file.filename or "upload"
    suffix = _suffix(filename)

    if suffix not in ACCEPTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Accepted: {', '.join(sorted(ACCEPTED_TYPES))}",
        )

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data) // 1024} KB). Maximum is {MAX_FILE_BYTES // 1024} KB.",
        )

    # Run extraction in a thread (pdfplumber and python-docx are synchronous and CPU-bound)
    def _extract() -> str:
        if suffix == ".pdf":
            return _extract_text_pdf(data)
        if suffix == ".docx":
            return _extract_text_docx(data)
        return _extract_text_plain(data)

    try:
        raw_text = await asyncio.to_thread(_extract)
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {err}")

    truncated = len(raw_text) > MAX_TEXT_CHARS
    text = raw_text[:MAX_TEXT_CHARS] + ("\n[...truncated]" if truncated else "")

    return JSONResponse({
        "text": text,
        "name": filename,
        "truncated": truncated,
        "chars": len(text),
    })
