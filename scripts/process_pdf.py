#!/usr/bin/env python3
"""
PDF metadata helper for scientific document renaming.

Commands:
  extract <pdf_path>              Extract text, detect DOI, detect if image-only
  ocr <pdf_path>                  OCR via tesseract, returns plain text + DOI
  crossref_doi <doi>              Look up metadata by DOI via CrossRef
  crossref_search <query>         Search CrossRef by title/author keywords
  rename <pdf_path> <author> <title> <year>   Rename file in place
  list <folder_path>              List all PDF files in folder
  format <author> <title> <year>  Preview formatted filename without renaming

All commands return JSON to stdout.
"""

import sys
import json
import re
import os
import unicodedata
import urllib.request
import urllib.parse
import urllib.error


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(pdf_path):
    """Extract text from PDF. Returns {text, first_page_text, doi, is_image_only, page_count}."""
    try:
        import fitz
    except ImportError:
        return {"error": "pymupdf not installed. Run: pip3 install pymupdf"}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {"error": f"Could not open PDF: {e}"}

    page_count = len(doc)
    full_text = ""
    first_page_text = ""

    for page_num in range(min(page_count, 5)):
        page_text = doc[page_num].get_text()
        if page_num == 0:
            first_page_text = page_text
        full_text += page_text

    doc.close()

    # Image-only detection: very little extractable text
    is_image_only = len(full_text.strip()) < 100 and page_count > 0

    doi = find_doi(full_text)

    return {
        "text": full_text[:3000],
        "first_page_text": first_page_text[:2000],
        "doi": doi,
        "is_image_only": is_image_only,
        "page_count": page_count,
    }


def find_doi(text):
    """Find a DOI in text. Returns the DOI string or None."""
    patterns = [
        r'https?://doi\.org/(10\.\d{4,9}/\S+)',
        r'\bdoi:\s*(10\.\d{4,9}/\S+)',
        r'\bDOI:\s*(10\.\d{4,9}/\S+)',
        r'\b(10\.\d{4,9}/[^\s\'"<>()\[\]]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(1)
            # Strip trailing punctuation that often gets captured
            doi = re.sub(r'[.,;:\])\}]+$', '', doi)
            return doi
    return None


# ---------------------------------------------------------------------------
# OCR via Tesseract
# ---------------------------------------------------------------------------

def ocr_tesseract(pdf_path):
    """OCR a PDF using Tesseract. Returns {text, first_page_text, doi}."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        return {"error": "pdf2image or pytesseract not installed. Run: pip3 install pdf2image pytesseract"}

    try:
        pages = convert_from_path(pdf_path, first_page=1, last_page=3, dpi=200)
    except Exception as e:
        return {"error": f"Could not convert PDF to images: {e}"}

    full_text = ""
    first_page_text = ""

    for i, page in enumerate(pages):
        try:
            page_text = pytesseract.image_to_string(page, lang="eng")
        except Exception as e:
            return {"error": f"Tesseract OCR failed on page {i+1}: {e}"}
        if i == 0:
            first_page_text = page_text
        full_text += page_text

    doi = find_doi(full_text)

    return {
        "text": full_text[:3000],
        "first_page_text": first_page_text[:2000],
        "doi": doi,
        "is_image_only": True,
        "ocr_method": "tesseract",
    }


# ---------------------------------------------------------------------------
# CrossRef API
# ---------------------------------------------------------------------------

def crossref_doi(doi):
    """Look up metadata by DOI via CrossRef. Returns {author, title, year, doi, type}."""
    encoded = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "scientific-pdf-skill/1.0 (mailto:user@example.com)"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        return {"error": f"CrossRef HTTP {e.code} for DOI: {doi}"}
    except Exception as e:
        return {"error": str(e)}

    if data.get("status") != "ok":
        return {"error": "DOI not found in CrossRef"}

    return parse_crossref_work(data["message"])


def crossref_search(query):
    """Search CrossRef by keywords. Returns {results: [...top 3...]}."""
    params = urllib.parse.urlencode({
        "query": query,
        "rows": 3,
        "select": "DOI,title,author,published,published-print,published-online,issued,type",
    })
    url = f"https://api.crossref.org/works?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "scientific-pdf-skill/1.0 (mailto:user@example.com)"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except Exception as e:
        return {"error": str(e)}

    items = data.get("message", {}).get("items", [])
    return {"results": [parse_crossref_work(item) for item in items]}


# ---------------------------------------------------------------------------
# Semantic Scholar API (good fallback for arXiv/preprints)
# ---------------------------------------------------------------------------

def semantic_search(query):
    """Search Semantic Scholar by keywords. Returns {results: [...top 3...]}."""
    params = urllib.parse.urlencode({
        "query": query,
        "limit": 3,
        "fields": "title,authors,year,externalIds,publicationTypes",
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "scientific-pdf-skill/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except Exception as e:
        return {"error": str(e)}

    results = []
    for paper in data.get("data", []):
        authors = paper.get("authors", [])
        if not authors:
            author_str = "Unknown"
        elif len(authors) == 1:
            author_str = authors[0].get("name", "Unknown").split()[-1]  # last name
        elif len(authors) == 2:
            a1 = authors[0].get("name", "").split()[-1]
            a2 = authors[1].get("name", "").split()[-1]
            author_str = f"{a1} & {a2}"
        else:
            a1 = authors[0].get("name", "").split()[-1]
            author_str = f"{a1} et al."

        ext_ids = paper.get("externalIds", {})
        doi = ext_ids.get("DOI") or ext_ids.get("ArXiv") or ""

        results.append({
            "author": author_str,
            "title": paper.get("title", "Unknown Title"),
            "year": str(paper.get("year") or "Unknown"),
            "doi": doi,
            "type": ", ".join(paper.get("publicationTypes") or []),
        })

    return {"results": results}


def parse_crossref_work(work):
    """Parse a CrossRef work record into {author, title, year, doi, type}."""
    # Authors
    authors = work.get("author", [])
    if not authors:
        author_str = "Unknown"
    elif len(authors) == 1:
        author_str = authors[0].get("family") or authors[0].get("name") or "Unknown"
    elif len(authors) == 2:
        a1 = authors[0].get("family") or authors[0].get("name") or ""
        a2 = authors[1].get("family") or authors[1].get("name") or ""
        author_str = f"{a1} & {a2}"
    else:
        a1 = authors[0].get("family") or authors[0].get("name") or ""
        author_str = f"{a1} et al."

    # Title
    titles = work.get("title", [])
    title = titles[0] if titles else "Unknown Title"
    # Strip HTML tags sometimes present in CrossRef titles
    title = re.sub(r"<[^>]+>", "", title).strip()

    # Year — try several date fields in priority order
    year = None
    for field in ("published", "published-print", "published-online", "issued"):
        date_parts = work.get(field, {}).get("date-parts", [[]])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
            break
    if not year:
        year = "Unknown"

    return {
        "author": author_str,
        "title": title,
        "year": year,
        "doi": work.get("DOI", ""),
        "type": work.get("type", ""),
    }


# ---------------------------------------------------------------------------
# Filename formatting and renaming
# ---------------------------------------------------------------------------

def format_filename(author, title, year):
    """Format as 'Author - Title - Year.pdf', truncating title at ~40 chars."""
    # Prefer truncating at a subtitle boundary (colon) if the main title fits
    if len(title) > 40 and ":" in title:
        before_colon = title.split(":")[0].strip()
        if 10 <= len(before_colon) <= 40:
            title = before_colon

    # Otherwise truncate at word boundary near 40 chars
    if len(title) > 40:
        truncated = title[:40]
        last_space = truncated.rfind(" ")
        if last_space > 25:
            truncated = truncated[:last_space]
        title = truncated

    filename = f"{author} - {title} - {year}.pdf"
    return sanitize_filename(filename)


def sanitize_filename(name):
    """Replace filesystem-unsafe characters and normalize whitespace."""
    replacements = {
        "/": "-", "\\": "-", ":": "", "*": "", "?": "",
        '"': "'", "<": "", ">": "", "|": "-",
        ",": "", "\n": " ", "\r": " ", "\t": " ",
    }
    for char, replacement in replacements.items():
        name = name.replace(char, replacement)
    # Normalize unicode (e.g. composed accents)
    name = unicodedata.normalize("NFC", name)
    # Collapse multiple spaces
    name = re.sub(r" {2,}", " ", name).strip()
    return name


def rename_pdf(pdf_path, author, title, year):
    """Rename a PDF file in place. Returns {new_path, new_name}."""
    directory = os.path.dirname(os.path.abspath(pdf_path))
    new_name = format_filename(author, title, year)
    new_path = os.path.join(directory, new_name)

    abs_old = os.path.abspath(pdf_path)

    # If it would result in the same path, report success without touching
    if abs_old == os.path.abspath(new_path):
        return {"new_path": new_path, "new_name": new_name, "unchanged": True}

    # Handle name collision
    if os.path.exists(new_path):
        base = new_name[:-4]  # strip .pdf
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(directory, f"{base} ({counter}).pdf")
            counter += 1

    os.rename(abs_old, new_path)
    return {"new_path": new_path, "new_name": os.path.basename(new_path)}


def list_pdfs(folder_path):
    """List all PDF files in a folder (non-recursive, sorted)."""
    try:
        files = sorted(f for f in os.listdir(folder_path) if f.lower().endswith(".pdf"))
        return {
            "pdfs": [os.path.join(folder_path, f) for f in files],
            "count": len(files),
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command given. See script docstring for usage."}))
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "extract" and len(sys.argv) >= 3:
        print(json.dumps(extract_text(sys.argv[2])))

    elif cmd == "ocr" and len(sys.argv) >= 3:
        print(json.dumps(ocr_tesseract(sys.argv[2])))

    elif cmd == "crossref_doi" and len(sys.argv) >= 3:
        print(json.dumps(crossref_doi(sys.argv[2])))

    elif cmd == "crossref_search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        print(json.dumps(crossref_search(query)))

    elif cmd == "semantic_search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        print(json.dumps(semantic_search(query)))

    elif cmd == "rename" and len(sys.argv) >= 6:
        # rename <path> <author> <title> <year>
        print(json.dumps(rename_pdf(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])))

    elif cmd == "format" and len(sys.argv) >= 5:
        # format <author> <title> <year>
        result = format_filename(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps({"filename": result}))

    elif cmd == "list" and len(sys.argv) >= 3:
        print(json.dumps(list_pdfs(sys.argv[2])))

    else:
        print(json.dumps({"error": f"Unknown command or missing arguments: {' '.join(sys.argv[1:])}"}))
        sys.exit(1)
