---
name: rename-scientific-pdf
description: Rename scientific PDFs (journal articles, book chapters, preprints, theses) using structured Author - Title - Year metadata resolved via DOI lookup or content analysis — exactly like Zotero does. Handles image-only PDFs with OCR. Use this skill whenever the user wants to rename, organize, or identify a scientific PDF or a folder of papers, or asks to find metadata for a PDF. Even if the user just says "rename this paper" or "organize my PDFs", invoke this skill.
---

# Scientific PDF Renamer

Rename scientific PDF files to a clean `Author - Title - Year.pdf` schema, with metadata resolved via CrossRef DOI lookup or content-based search.

## Script

All PDF operations use `scripts/process_pdf.py` (bundled with this skill). Run it as:

```bash
python3 "<skill_dir>/scripts/process_pdf.py" <command> [args]
```

Replace `<skill_dir>` with the absolute path to this skill's directory.

---

## Workflow

### Step 0: First-time setup (ask once per session, before processing anything)

Ask these two questions upfront — not mid-processing. Store the answers and use them for the entire session.

**Question 1 — OCR method** (for image-only PDFs):
> "If I find a PDF that contains no readable text (e.g. a scanned document), which OCR method should I use?
> (a) Tesseract — fast, local, no extra cost
> (b) Claude vision — slower, uses tokens, but more accurate for complex scientific layouts"

**Question 2 — Uncertain metadata**:
> "When I can't confidently identify a paper's metadata (no DOI found, and search results look shaky), should I:
> (a) Show you my best guess and ask for confirmation
> (b) Skip renaming that file and note it in the summary"

---

### Step 1: Collect files

- **Single file** → use the path directly
- **Folder** → list all PDFs:
  ```bash
  python3 "<script>" list "<folder_path>"        # top level only
  python3 "<script>" list "<folder_path>" -r     # recurse into subfolders
  ```
  Returns `{pdfs: [...], count: N, recursive: bool}`. Use `-r` when the user asks to process a folder *and its subfolders* (e.g. a nested library); otherwise default to the top level.

---

### Step 2: Process each PDF

#### 2a. Extract text

```bash
python3 "<script>" extract "<pdf_path>"
```

Returns `{text, first_page_text, doi, is_image_only, page_count}`.

#### 2b. Handle image-only PDFs

If `is_image_only: true` (fewer than ~100 chars of extractable text):

- **Tesseract**: `python3 "<script>" ocr "<pdf_path>" [lang]` → returns `{text, first_page_text, doi}`. `lang` is optional (e.g. `eng+deu+fra`); it defaults to the `TESSERACT_LANG` env var, then `eng`. For non-English scans, pass the right language(s) — the corresponding Tesseract language packs must be installed.
- **Claude vision**: Use the `Read` tool on the PDF file path to view the pages visually, then extract text, DOI, title, and authors yourself from what you see.

#### 2c. Resolve metadata

**If a DOI was found** → query CrossRef:
```bash
python3 "<script>" crossref_doi "<doi>"
```
Returns `{author, title, year, doi, type}`. This is authoritative — use it directly.

**Special case — ResearchGate DOIs** (`10.13140/RG.*`): these are not indexed in CrossRef. Skip the DOI lookup and fall back to content extraction below.

**If no DOI (or DOI lookup failed)** → extract title/author hints from `first_page_text`, then search:

```bash
python3 "<script>" crossref_search "<title keywords or author name + key words>"
```

If CrossRef returns nothing useful (common for arXiv/bioRxiv preprints), fall back to Semantic Scholar:

```bash
python3 "<script>" semantic_search "<title keywords>"
```

Both return `{results: [{author, title, year, doi}, ...]}` — top 3 matches. Pick the best fit by comparing returned titles and authors against what you see in the PDF's first-page text.

**When search also fails, or for self-published reports**: if `first_page_text` already contains a clear title, author, and year (common on ResearchGate cover pages, technical reports, and theses), you can read those directly from the text and skip API search entirely. Use these values and note in the summary that metadata came from the document itself rather than a database. A confident match is one where the title clearly aligns and the authors look right.

**Year sanity check**: Some papers have been re-uploaded to new platforms years later, causing CrossRef to return the wrong year. Always cross-check the year from the metadata against any year visible on the PDF's first page (submission date, "Published:", copyright year, or conference name like "NeurIPS 2017"). If there is a meaningful discrepancy, trust what the PDF itself says.

**If confidence is low** → apply the user's preference from Step 0:
- Ask → show the best guess and wait for confirmation or a correction
- Skip → note the file in the summary and move on

---

### Step 3: Rename

Once you have `author`, `title`, `year`:

```bash
python3 "<script>" rename "<pdf_path>" "<author>" "<title>" "<year>"
```

Returns `{new_path, new_name}`.

**Naming schema** (all handled by the script):
- 1 author: `Smith`
- 2 authors: `Smith & Jones`
- 3+ authors: `Smith et al.`
- Title: truncated at ~40 chars at a word boundary
- Example: `Smith et al. - Attention Is All You Need - 2017.pdf`

You do **not** need to format the author string yourself — the CrossRef results already come in the right format. Just pass what the script returned.

---

### Step 4: Summary report

After all files are processed, print a compact table:

```
Renamed (4):
  ✓  old_name.pdf
     → Smith et al. - Attention Is All You Need - 2017.pdf

  ✓  paper2.pdf
     → Jones & Lee - Deep Learning for Natural Lang - 2020.pdf

Skipped — uncertain metadata (1):
  -  weird_scan.pdf  (no DOI, top search result: "Smith 2003" — didn't match)

Errors (0):
```

---

## Dependencies

Required Python packages (install once):
```bash
pip3 install -r requirements.txt   # pymupdf pdf2image pytesseract
brew install tesseract poppler     # macOS — only needed for Tesseract OCR
# sudo apt install tesseract-ocr poppler-utils   # Debian/Ubuntu
```

`pymupdf` (fitz) handles text extraction and is the only hard requirement. The Tesseract OCR path additionally needs `pdf2image` + `pytesseract` plus the `tesseract` and `poppler` system binaries (poppler is what `pdf2image` uses to rasterize pages). Claude vision needs no additional setup.

CrossRef is queried without an API key — the script sends a polite `User-Agent` header. Set `CROSSREF_MAILTO=you@example.com` to include a contact address as recommended by CrossRef's etiquette guidelines. Non-English OCR: set `TESSERACT_LANG` (e.g. `eng+deu+fra`) or pass the language as the optional `ocr` argument.

---

## Edge cases

- **No year found**: use `"Unknown"` and note it in the summary
- **Institutional/corporate authors** (e.g. "WHO"): use the organization name as-is
- **Name collisions**: the script appends `(1)`, `(2)`, etc. automatically
- **Already well-named files**: if the current filename already matches the schema, still verify and rename (the script handles no-op renames gracefully)
