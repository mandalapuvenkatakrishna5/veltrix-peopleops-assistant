import json, os, re
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
from .config import CORPUS_DIR, MANIFEST_PATH

def read_file(path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            txt = page.extract_text() or ""
            if not txt.strip():
                # OCR is automatic; requires tesseract and poppler in runtime.
                try:
                    import fitz, pytesseract
                    from PIL import Image
                    import io
                    pdf = fitz.open(str(path))
                    pix = pdf[i-1].get_pixmap(matrix=fitz.Matrix(2,2))
                    txt = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))
                except Exception:
                    txt = ""
            pages.append((i, txt))
        return pages
    if ext == ".docx":
        d = Document(str(path))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for ti, table in enumerate(d.tables, 1):
            parts.append(f"Table {ti}:\n" + "\n".join(" | ".join(c.text.strip() for c in row.cells) for row in table.rows))
        return [(None, "\n".join(parts))]
    if ext == ".md":
        return [(None, path.read_text(encoding="utf-8"))]
    if ext in (".html", ".htm"):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for table in soup.find_all("table"):
            table.insert_before(soup.new_string("\n" + " | ".join(c.get_text(" ",strip=True) for c in table.find_all(["th","td"])) + "\n"))
        return [(None, soup.get_text("\n", strip=True))]
    raise ValueError(f"Unsupported document format: {ext}")

def split_chunks(text, page=None, max_chars=1100, overlap=150):
    # Split by headings/paragraphs first, then cap long paragraphs.
    paras = re.split(r"\n\s*\n|(?=^#{1,6}\s)", text, flags=re.M)
    chunks, cur = [], ""
    for para in paras:
        para = para.strip()
        if not para: continue
        while len(para) > max_chars:
            if cur: chunks.append(cur); cur = ""
            chunks.append(para[:max_chars])
            para = para[max_chars-overlap:]
        if len(cur) + len(para) + 2 > max_chars and cur:
            chunks.append(cur); cur = para
        else:
            cur = (cur + "\n\n" + para).strip()
    if cur: chunks.append(cur)
    result=[]
    for i, chunk in enumerate(chunks):
        headings=re.findall(r"(?m)^#{1,6}\s+(.+)$|^([A-Z][^\n]{2,80})$", chunk)
        heading=next((a or b for a,b in headings if a or b), None)
        locator=heading or (f"p. {page}" if page else f"section {i+1}")
        result.append({"text":chunk,"locator":locator})
    return result

def ingest():
    manifest=json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
    docs=[]
    for meta in manifest:
        path=Path(CORPUS_DIR)/meta["file"]
        if not path.exists(): raise FileNotFoundError(f"Manifest document missing: {meta['file']}")
        for page, text in read_file(path):
            for chunk in split_chunks(text, page):
                docs.append({**meta, "text":chunk["text"], "locator":chunk["locator"], "page":page})
    if not docs: raise RuntimeError("No corpus content ingested")
    return docs
