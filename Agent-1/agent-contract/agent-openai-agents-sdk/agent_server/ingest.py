"""Ingestion helpers -- upload documents, OCR via vision model, embed, write bundle.

Supported formats: PDF, MSG, PPTX, XLSX/XLS, HTML/HTM/MHT, PNG/BMP/JPG.
"""

import base64
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests as http_requests
from databricks.sdk import WorkspaceClient

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _staging_volume() -> str:
    """Root of the writable staging volume."""
    return os.getenv(
        "STAGING_BUNDLE_BASE",
        "/Volumes/mdna_dev/warranty_agent_staging/uploads",
    ).rstrip("/")


def staging_bundle_base() -> str:
    return f"{_staging_volume()}/kb_bundle"


def staging_raw_dir(oem: str, kb_id: str) -> str:
    return f"{_staging_volume()}/raw/{oem}/{kb_id}"


def _vision_endpoint() -> str:
    return (os.getenv("VISION_ENDPOINT") or "databricks-claude-opus-4-8").strip()


def _embedding_endpoint() -> str:
    return (os.getenv("EMBEDDING_ENDPOINT") or "databricks-gte-large-en").strip()


# Max base64 bytes per image to stay safely under the 1M token API limit.
# 600KB base64 ≈ 150K tokens, leaving ample room for prompt text.
_MAX_B64_BYTES = 600_000

# Vision OCR timeout: 10 minutes per page (scanned PDFs can be slow)
_VISION_TIMEOUT_SECONDS = 600


# ---------------------------------------------------------------------------
# Upload files to staging
# ---------------------------------------------------------------------------

def upload_files(
    wc: WorkspaceClient,
    oem: str,
    kb_id: str,
    files: list[tuple[str, bytes]],
) -> list[str]:
    """Write uploaded file bytes to staging volume."""
    dest_dir = staging_raw_dir(oem, kb_id)
    paths = []
    for fname, data in files:
        p = f"{dest_dir}/{fname}"
        wc.files.upload(p, io.BytesIO(data), overwrite=True)
        paths.append(p)
        log.info("Uploaded %s (%d bytes)", p, len(data))
    return paths


upload_pdfs = upload_files


# ---------------------------------------------------------------------------
# Auth helper for direct HTTP calls
# ---------------------------------------------------------------------------

def _get_auth_headers(wc: WorkspaceClient) -> dict:
    """Extract auth headers from a WorkspaceClient for direct HTTP calls."""
    headers = {}

    # Method 1: Use SDK's header_factory (works for all auth types)
    try:
        header_factory = wc.config.authenticate
        if callable(header_factory):
            result = header_factory()
            if callable(result):
                result(headers)
            elif isinstance(result, dict):
                headers = result
        if headers:
            return headers
    except Exception:
        pass

    # Method 2: Direct token access (works for SP and PAT auth)
    token = getattr(wc.config, "token", None)
    if token:
        return {"Authorization": f"Bearer {token}"}

    raise RuntimeError("Cannot extract auth headers from WorkspaceClient")


# ---------------------------------------------------------------------------
# Text extraction: pypdf (fast) + vision OCR (fallback for scanned PDFs)
# ---------------------------------------------------------------------------

def _extract_text_pypdf(pdf_bytes: bytes) -> tuple[list[dict], int]:
    """Extract text using pypdf. Fast but fails on scanned/image PDFs.

    Returns (pages_with_text, total_page_count).
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], 0

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages, total_pages


def _pixmap_to_jpeg(pix, quality: int = 80) -> tuple[bytes, str]:
    """Convert a PyMuPDF Pixmap to JPEG bytes using Pillow.

    Returns (image_bytes, media_type).
    Falls back to PNG if Pillow is not available.
    """
    try:
        from PIL import Image

        # Convert PyMuPDF Pixmap → PIL Image
        if pix.alpha:
            img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
            img = img.convert("RGB")
        else:
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        # Pillow not available — fall back to PNG
        return pix.tobytes("png"), "image/png"


def _pdf_pages_to_images(
    pdf_bytes: bytes,
    max_b64_bytes: int = _MAX_B64_BYTES,
) -> list[tuple[int, bytes, str]]:
    """Convert PDF pages to compressed images using PyMuPDF.

    Adaptively reduces DPI until each page's base64 encoding is under
    *max_b64_bytes*, ensuring it fits within API token limits regardless
    of the source PDF resolution or page count.

    Returns list of (page_number, image_bytes, media_type).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[tuple[int, bytes, str]] = []

    for i, page in enumerate(doc):
        img_bytes = b""
        media_type = "image/png"

        # Try progressively lower DPIs until the image fits
        for dpi in (150, 120, 100, 72):
            pix = page.get_pixmap(dpi=dpi)
            img_bytes, media_type = _pixmap_to_jpeg(pix, quality=80)

            b64_len = ((len(img_bytes) + 2) // 3) * 4  # exact base64 length
            if b64_len <= max_b64_bytes:
                break

            log.debug(
                "Page %d at %d DPI: %dKB (b64 %dKB) — too large, reducing",
                i + 1, dpi, len(img_bytes) // 1024, b64_len // 1024,
            )

        # Final safety: if still too large at 72 DPI, reduce JPEG quality
        b64_len = ((len(img_bytes) + 2) // 3) * 4
        if b64_len > max_b64_bytes and media_type == "image/jpeg":
            try:
                from PIL import Image
                pix = page.get_pixmap(dpi=72)
                if pix.alpha:
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples).convert("RGB")
                else:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                for q in (60, 40, 20):
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=q, optimize=True)
                    img_bytes = buf.getvalue()
                    b64_len = ((len(img_bytes) + 2) // 3) * 4
                    if b64_len <= max_b64_bytes:
                        break
            except ImportError:
                pass  # no Pillow, can't compress further

        log.info(
            "Page %d: %dKB image (%s), b64 %dKB",
            i + 1, len(img_bytes) // 1024, media_type,
            ((len(img_bytes) + 2) // 3) * 4 // 1024,
        )
        images.append((i + 1, img_bytes, media_type))

    doc.close()
    return images


def _ocr_page_vision(
    wc: WorkspaceClient,
    page_num: int,
    img_bytes: bytes,
    media_type: str,
    endpoint: str,
) -> str:
    """Send a single page image to a vision model for OCR extraction.

    Uses direct HTTP with OpenAI-compatible multimodal format and a
    10-minute timeout (SDK default is 5 min which is too short for
    dense scanned pages).
    """
    b64 = base64.b64encode(img_bytes).decode("ascii")
    data_uri = f"data:{media_type};base64,{b64}"

    host = wc.config.host.rstrip("/")
    auth_headers = _get_auth_headers(wc)

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL text from this document page exactly as written. "
                            "Preserve paragraph structure, headings, bullet points, and table layouts. "
                            "For tables, use | delimited format. "
                            "Return ONLY the extracted text, no commentary."
                        ),
                    },
                ],
            }
        ],
        "max_tokens": 16000,
        "temperature": 0.0,
    }

    log.info(
        "Vision OCR page %d: sending %dKB image to %s (timeout=%ds)",
        page_num, len(img_bytes) // 1024, endpoint, _VISION_TIMEOUT_SECONDS,
    )

    resp = http_requests.post(
        f"{host}/serving-endpoints/{endpoint}/invocations",
        json=payload,
        headers={"Content-Type": "application/json", **auth_headers},
        timeout=_VISION_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()

    text = data["choices"][0]["message"]["content"].strip()
    log.info("Vision OCR page %d: extracted %d chars", page_num, len(text))
    return text


def _extract_text_vision(
    wc: WorkspaceClient,
    pdf_bytes: bytes,
    progress_callback=None,
) -> list[dict]:
    """Extract text from a scanned PDF using vision OCR (Claude Opus 4.6)."""
    endpoint = _vision_endpoint()
    images = _pdf_pages_to_images(pdf_bytes)

    pages = []
    for page_num, img_bytes, media_type in images:
        if progress_callback:
            progress_callback(f"  OCR page {page_num}/{len(images)}...")
        try:
            text = _ocr_page_vision(wc, page_num, img_bytes, media_type, endpoint)
            if text and len(text.strip()) > 10:
                pages.append({"page": page_num, "text": text.strip()})
        except Exception as e:
            log.warning("Vision OCR failed on page %d: %s", page_num, e)
            continue
    return pages


def _extract_text_smart(
    wc: WorkspaceClient,
    pdf_bytes: bytes,
    fname: str,
    progress_callback=None,
) -> list[dict]:
    """Smart extraction: try pypdf first, fall back to vision OCR if needed.

    Falls back to vision OCR when:
    - pypdf extracts < 50 chars/page average, OR
    - pypdf extracts text from < 50% of total pages (scanned PDF signature), OR
    - pypdf extracts nothing at all
    """
    # Try pypdf first (fast)
    pages, total_pages = _extract_text_pypdf(pdf_bytes)

    pypdf_good = False
    if pages and total_pages > 0:
        avg_len = sum(len(p["text"]) for p in pages) / len(pages)
        coverage = len(pages) / total_pages

        if avg_len >= 50 and coverage >= 0.5:
            log.info(
                "%s: pypdf extracted %d/%d pages (%.0f%% coverage, avg %d chars) -- using pypdf",
                fname, len(pages), total_pages, coverage * 100, int(avg_len),
            )
            pypdf_good = True
        else:
            log.info(
                "%s: pypdf weak extraction: %d/%d pages (%.0f%% coverage, avg %d chars) "
                "-- falling back to vision OCR",
                fname, len(pages), total_pages, coverage * 100, int(avg_len),
            )

    if pypdf_good:
        return pages

    # Fall back to vision OCR
    if progress_callback:
        progress_callback(f"  {fname}: using vision OCR (scanned PDF detected)...")

    try:
        vision_pages = _extract_text_vision(wc, pdf_bytes, progress_callback)
        if vision_pages:
            avg_len = sum(len(p["text"]) for p in vision_pages) / len(vision_pages)
            log.info("%s: vision OCR extracted %d pages (avg %d chars)",
                     fname, len(vision_pages), int(avg_len))
            return vision_pages
    except ImportError:
        log.warning("%s: PyMuPDF (fitz) not installed -- cannot do vision OCR", fname)
    except Exception as e:
        log.warning("%s: vision OCR failed: %s", fname, e)

    # Return whatever pypdf got (even if sparse)
    return pages


# ---------------------------------------------------------------------------
# Text extraction: MSG (Outlook emails)
# ---------------------------------------------------------------------------

def _extract_text_msg(msg_bytes: bytes, **_kwargs) -> list[dict]:
    """Extract text from an Outlook .msg file (subject, sender, date, body)."""
    try:
        import extract_msg
    except ImportError:
        log.warning("extract-msg not installed -- cannot process .msg files")
        return []

    try:
        msg = extract_msg.Message(io.BytesIO(msg_bytes))
        parts = []
        if msg.subject:
            parts.append(f"Subject: {msg.subject}")
        if msg.sender:
            parts.append(f"From: {msg.sender}")
        if msg.date:
            parts.append(f"Date: {msg.date}")
        if msg.body:
            parts.append(f"\n{msg.body.strip()}")

        text = "\n".join(parts).strip()
        pages = [{"page": 1, "text": text}] if text else []

        for att in (msg.attachments or []):
            att_name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", "") or ""
            att_data = getattr(att, "data", None)
            if not att_data or not att_name:
                continue
            ext = os.path.splitext(att_name)[1].lower()
            if ext in _FORMAT_EXTRACTORS and ext != ".msg":
                try:
                    att_pages = _extract_text_by_format(
                        None, att_data, att_name, progress_callback=None
                    )
                    for p in att_pages:
                        p["text"] = f"[Attachment: {att_name}]\n{p['text']}"
                    pages.extend(att_pages)
                except Exception as exc:
                    log.debug("Could not extract MSG attachment %s: %s", att_name, exc)

        msg.close()
        return pages
    except Exception as exc:
        log.warning("MSG extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Text extraction: PPTX (PowerPoint)
# ---------------------------------------------------------------------------

def _extract_text_pptx(pptx_bytes: bytes, **_kwargs) -> list[dict]:
    """Extract slide text and speaker notes from a PowerPoint file."""
    try:
        from pptx import Presentation
    except ImportError:
        log.warning("python-pptx not installed -- cannot process .pptx files")
        return []

    try:
        prs = Presentation(io.BytesIO(pptx_bytes))
        pages = []
        for slide_num, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        line = para.text.strip()
                        if line:
                            texts.append(line)
                if shape.has_table:
                    for row in shape.table.rows:
                        row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_vals:
                            texts.append(" | ".join(row_vals))
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    texts.append(f"[Speaker notes] {notes}")
            text = "\n".join(texts).strip()
            if text:
                pages.append({"page": slide_num, "text": text})
        return pages
    except Exception as exc:
        log.warning("PPTX extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Text extraction: XLSX / XLS (Excel)
# ---------------------------------------------------------------------------

_XLSX_MAX_ROWS = 5000

def _extract_text_xlsx(xlsx_bytes: bytes, **_kwargs) -> list[dict]:
    """Extract text from Excel spreadsheets, one 'page' per sheet."""
    try:
        import openpyxl
    except ImportError:
        log.warning("openpyxl not installed -- cannot process .xlsx files")
        return []

    try:
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
        pages = []
        for sheet_num, ws in enumerate(wb.worksheets, 1):
            lines = []
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                row_count += 1
                if row_count > _XLSX_MAX_ROWS:
                    lines.append(f"[... truncated at {_XLSX_MAX_ROWS} rows ...]")
                    break
                vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if vals:
                    lines.append(" | ".join(vals))
            text = f"Sheet: {ws.title}\n" + "\n".join(lines)
            text = text.strip()
            if text and len(text) > len(f"Sheet: {ws.title}"):
                pages.append({"page": sheet_num, "text": text})
        wb.close()
        return pages
    except Exception as exc:
        log.warning("XLSX extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Text extraction: HTML / HTM / MHT
# ---------------------------------------------------------------------------

def _extract_text_html(html_bytes: bytes, **_kwargs) -> list[dict]:
    """Extract visible text from HTML or MHT files."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed -- cannot process HTML files")
        return []

    try:
        raw = html_bytes
        content_type = "html"

        decoded = html_bytes.decode("utf-8", errors="ignore")
        if decoded.lstrip().startswith("From:") or "Content-Type:" in decoded[:500]:
            content_type = "mht"
            import email.parser
            msg = email.parser.Parser().parsestr(decoded)
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type() or ""
                    if "html" in ct:
                        payload = part.get_payload(decode=True)
                        if payload:
                            raw = payload
                            break
                    elif "plain" in ct and raw == html_bytes:
                        payload = part.get_payload(decode=True)
                        if payload:
                            raw = payload
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    raw = payload

        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "meta", "link"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if text and len(text.strip()) > 10:
            return [{"page": 1, "text": text.strip()}]
        return []
    except Exception as exc:
        log.warning("HTML/MHT extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Text extraction: Images (PNG, BMP, JPG) via vision OCR
# ---------------------------------------------------------------------------

def _extract_text_image(
    wc: WorkspaceClient | None,
    img_bytes: bytes,
    fname: str = "",
    progress_callback=None,
    **_kwargs,
) -> list[dict]:
    """Extract text from an image file using vision OCR."""
    if wc is None:
        log.warning("WorkspaceClient required for image OCR -- skipping %s", fname)
        return []

    ext = os.path.splitext(fname)[1].lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")

    if ext == ".bmp":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            media_type = "image/png"
        except ImportError:
            log.warning("Pillow needed to convert BMP to PNG for OCR")
            return []

    b64_len = ((len(img_bytes) + 2) // 3) * 4
    if b64_len > _MAX_B64_BYTES:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            for q in (70, 50, 30):
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=q, optimize=True)
                img_bytes = buf.getvalue()
                media_type = "image/jpeg"
                b64_len = ((len(img_bytes) + 2) // 3) * 4
                if b64_len <= _MAX_B64_BYTES:
                    break
        except ImportError:
            pass

    try:
        endpoint = _vision_endpoint()
        if progress_callback:
            progress_callback(f"  OCR image {fname}...")
        text = _ocr_page_vision(wc, 1, img_bytes, media_type, endpoint)
        if text and len(text.strip()) > 10:
            return [{"page": 1, "text": text.strip()}]
        return []
    except Exception as exc:
        log.warning("Image OCR failed for %s: %s", fname, exc)
        return []


# ---------------------------------------------------------------------------
# Format router
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = frozenset({
    ".pdf", ".msg", ".pptx",
    ".xlsx", ".xls",
    ".htm", ".html", ".mht",
    ".png", ".bmp", ".jpg", ".jpeg",
})

_NEEDS_WORKSPACE_CLIENT = frozenset({".pdf", ".png", ".bmp", ".jpg", ".jpeg"})


def _extract_text_by_format(
    wc: WorkspaceClient | None,
    file_bytes: bytes,
    filename: str,
    progress_callback=None,
) -> list[dict]:
    """Route to the correct text extractor based on file extension."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        if wc is None:
            log.warning("WorkspaceClient required for PDF OCR fallback")
            pages, _ = _extract_text_pypdf(file_bytes)
            return pages
        return _extract_text_smart(wc, file_bytes, filename, progress_callback)
    elif ext == ".msg":
        return _extract_text_msg(file_bytes)
    elif ext == ".pptx":
        return _extract_text_pptx(file_bytes)
    elif ext in (".xlsx", ".xls"):
        return _extract_text_xlsx(file_bytes)
    elif ext in (".htm", ".html", ".mht"):
        return _extract_text_html(file_bytes)
    elif ext in (".png", ".bmp", ".jpg", ".jpeg"):
        return _extract_text_image(wc, file_bytes, filename, progress_callback)
    else:
        log.warning("Unsupported file format: %s (from %s)", ext, filename)
        return []


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chars: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks, sentence-aware."""
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?;])\s+", text)
    chunks: list[str] = []
    cur = ""

    def flush(buf: str) -> str:
        chunks.append(buf.strip())
        if overlap > 0 and len(buf) > overlap:
            tail = buf[-overlap:]
            sp = tail.find(" ")
            return tail[sp + 1:] if sp > 0 else tail
        return ""

    for sent in sentences:
        if len(sent) > max_chars:
            if cur.strip():
                cur = flush(cur)
            words = sent.split()
            buf = cur
            for w in words:
                cand = f"{buf} {w}".strip() if buf else w
                if len(cand) > max_chars:
                    if buf.strip():
                        buf = flush(buf)
                        buf = f"{buf} {w}".strip() if buf else w
                    else:
                        chunks.append(w)
                        buf = ""
                else:
                    buf = cand
            cur = buf
            continue

        cand = f"{cur} {sent}".strip() if cur else sent
        if len(cand) > max_chars:
            seed = flush(cur)
            cur = f"{seed} {sent}".strip() if seed else sent
        else:
            cur = cand

    if cur.strip():
        chunks.append(cur.strip())
    return chunks


# ---------------------------------------------------------------------------
# Embedding computation
# ---------------------------------------------------------------------------

def _compute_embeddings(
    wc: WorkspaceClient,
    texts: list[str],
    batch_size: int = 50,
    progress_callback=None,
) -> list[list[float]]:
    """Compute embeddings for a list of texts using the embedding endpoint."""
    ep = _embedding_endpoint()
    if not ep:
        return [[] for _ in texts]

    all_embeddings: list[list[float]] = []
    total_batches = (len(texts) - 1) // batch_size + 1

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch = [t if t.strip() else "empty" for t in batch]
        batch_num = i // batch_size + 1

        if progress_callback:
            progress_callback(f"  Embedding batch {batch_num}/{total_batches}...")

        try:
            resp = wc.serving_endpoints.query(name=ep, input=batch)
            for item in resp.data:
                all_embeddings.append(item.embedding)
        except Exception as e:
            log.warning("Embedding batch %d failed: %s", batch_num, e)
            all_embeddings.extend([[] for _ in batch])

    return all_embeddings


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest_inline(
    wc: WorkspaceClient,
    oem: str,
    kb_id: str,
    files: list[tuple[str, bytes]] | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    progress_callback=None,
    *,
    pdf_files: list[tuple[str, bytes]] | None = None,
) -> dict[str, Any]:
    """Process documents in-process: extract text, chunk, embed, write bundle.

    Accepts any supported format (PDF, MSG, PPTX, XLSX, HTML, images).
    The ``pdf_files`` kwarg is kept for backward compatibility.
    """
    file_list = files or pdf_files or []

    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)
        log.info(msg)

    _progress(f"Processing {len(file_list)} file(s) for {oem}/{kb_id}...")

    all_rows: list[dict] = []
    failed_docs: list[str] = []

    for doc_idx, (fname, file_bytes) in enumerate(file_list):
        _progress(f"Parsing {fname} ({doc_idx + 1}/{len(file_list)})...")
        pages = _extract_text_by_format(wc, file_bytes, fname, progress_callback)

        if not pages:
            log.warning("No text extracted from %s", fname)
            failed_docs.append(fname)
            continue

        ext = os.path.splitext(fname)[1].lower()
        slug = re.sub(rf"(?i)\{re.escape(ext)}$", "", fname) if ext else fname
        slug = re.sub(r"[^A-Za-z0-9]+", "_", slug).strip("_").lower() or "doc"
        source_path = f"{staging_raw_dir(oem, kb_id)}/{fname}"

        for page_info in pages:
            page_num = page_info["page"]
            page_text = page_info["text"]
            text_chunks = _chunk_text(page_text, chunk_size, chunk_overlap)

            for chunk_idx, chunk_text in enumerate(text_chunks):
                chunk_id = hashlib.sha256(
                    f"{source_path}::{page_num}::{chunk_idx}::{chunk_text}".encode()
                ).hexdigest()

                all_rows.append({
                    "id": chunk_id,
                    "kb_id": kb_id,
                    "oem": oem,
                    "source_path": source_path,
                    "doc_slug": slug,
                    "element_pos": page_num,
                    "chunk_idx": chunk_idx,
                    "element_type": "text",
                    "text": chunk_text,
                    "full_text_len": len(page_text),
                    "page_number": page_num,
                    "parse_confidence": 1.0,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                })

    if not all_rows:
        return {
            "chunk_count": 0, "doc_count": 0, "status": "error",
            "message": f"No text extracted from any file. Failed: {failed_docs}",
        }

    _progress(f"Computing embeddings for {len(all_rows)} chunks...")
    texts = [r["text"] for r in all_rows]
    embeddings = _compute_embeddings(wc, texts, progress_callback=progress_callback)

    has_embeddings = False
    for row, emb in zip(all_rows, embeddings):
        if emb:
            row["embedding"] = emb
            has_embeddings = True

    _progress(f"Writing {len(all_rows)} chunks to staging bundle...")
    chunks_dir = f"{staging_bundle_base()}/chunks_json/oem={oem}/kb_id={kb_id}"
    jsonl_name = "part-00000-with-embeddings.json" if has_embeddings else "part-00000.json"
    jsonl = "\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows)
    wc.files.upload(
        f"{chunks_dir}/{jsonl_name}",
        io.BytesIO(jsonl.encode("utf-8")),
        overwrite=True,
    )

    _progress("Updating manifest...")
    doc_count = len(file_list) - len(failed_docs)
    update_staging_manifest(wc, oem, kb_id, len(all_rows), doc_count)

    status = "success" if not failed_docs else "partial"
    msg = f"{len(all_rows)} chunks from {doc_count} doc(s)."
    if has_embeddings:
        msg += f" Embeddings: {sum(1 for e in embeddings if e)}/{len(embeddings)}"
    if failed_docs:
        msg += f" Failed: {', '.join(failed_docs)}"

    _progress(f"Done! {msg}")
    return {
        "chunk_count": len(all_rows),
        "doc_count": doc_count,
        "failed_docs": failed_docs,
        "has_embeddings": has_embeddings,
        "status": status,
        "message": msg,
    }


# ---------------------------------------------------------------------------
# Trigger ingestion job (one-time run) -- requires Jobs permission
# ---------------------------------------------------------------------------

_NOTEBOOK_PATH = os.getenv(
    "INGEST_NOTEBOOK_PATH",
    "/Workspace/Users/adj1de@bosch.com/Warranty Agent/Warranty Agent Jobs/15_ingest_to_staging",
)


def trigger_ingest_job(
    wc: WorkspaceClient,
    oem: str,
    kb_id: str,
    cluster_id: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> int:
    """Submit a one-time job to ingest a contract (requires Jobs permission)."""
    from databricks.sdk.service.jobs import NotebookTask, SubmitTask

    nb_params = {
        "staging_base": _staging_volume(),
        "oem": oem,
        "kb_id": kb_id,
        "chunk_size": str(chunk_size),
        "chunk_overlap": str(chunk_overlap),
    }
    task = SubmitTask(
        task_key="ingest_contract",
        notebook_task=NotebookTask(
            notebook_path=_NOTEBOOK_PATH,
            base_parameters=nb_params,
            source="WORKSPACE",
        ),
    )
    if cluster_id:
        task.existing_cluster_id = cluster_id

    run = wc.jobs.submit(run_name=f"Ingest {oem}/{kb_id}", tasks=[task])
    log.info("Submitted run %s for %s/%s", run.run_id, oem, kb_id)
    return run.run_id


def get_run_status(wc: WorkspaceClient, run_id: int) -> dict[str, Any]:
    """Return simplified run status."""
    run = wc.jobs.get_run(run_id)
    state = run.state
    return {
        "run_id": run_id,
        "life_cycle_state": str(state.life_cycle_state) if state else "UNKNOWN",
        "result_state": str(state.result_state) if state and state.result_state else None,
        "state_message": state.state_message if state else "",
        "run_page_url": run.run_page_url,
    }


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def read_staging_manifest(wc: WorkspaceClient) -> list[dict]:
    path = f"{staging_bundle_base()}/manifest.json"
    try:
        raw = wc.files.download(path).contents.read()
        return json.loads(raw)
    except Exception:
        return []


def update_staging_manifest(
    wc: WorkspaceClient, oem: str, kb_id: str,
    chunk_count: int, doc_count: int,
) -> list[dict]:
    manifest = read_staging_manifest(wc)
    manifest = [m for m in manifest if not (m.get("oem") == oem and m.get("kb_id") == kb_id)]
    manifest.append({
        "oem": oem, "kb_id": kb_id,
        "chunk_count": chunk_count, "doc_count": doc_count,
        "bundle_path": f"{staging_bundle_base()}/chunks_json/oem={oem}/kb_id={kb_id}",
        "source": "staging",
    })
    path = f"{staging_bundle_base()}/manifest.json"
    wc.files.upload(path, io.BytesIO(json.dumps(manifest, indent=2).encode()), overwrite=True)
    log.info("Updated staging manifest: %d entries", len(manifest))
    return manifest
