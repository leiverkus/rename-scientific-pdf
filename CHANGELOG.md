# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-18

### Changed
- The `.skill` bundle is now a build artifact produced by
  `scripts/build_skill.sh` and attached to releases automatically by CI on any
  `v*` tag — it is no longer committed to the repository.

## [1.0.0] - 2026-06-18

First tagged release. The skill renames scientific PDFs to a clean
`Author - Title - Year.pdf` schema, resolving metadata the way Zotero does.

### Added
- DOI-based metadata lookup via CrossRef, with content-based fallback via
  CrossRef full-text search and Semantic Scholar (good for arXiv/preprints).
- OCR for image-only / scanned PDFs — Tesseract (local) or Claude vision.
- Configurable OCR language via the `TESSERACT_LANG` env var or an optional
  `ocr <pdf> [lang]` argument (e.g. `eng+deu+fra`), instead of English-only.
- Batch processing of folders, with optional recursion into subfolders
  (`list <folder> -r`).
- Naming schema with 1 / 2 / 3+ author handling, title truncation at a word
  boundary, collision handling, and a year sanity check against the first page.
- Configurable CrossRef contact email via `CROSSREF_MAILTO` (etiquette).
- `requirements.txt` and a GitHub Actions CI workflow (byte-compile + CLI
  smoke tests on Python 3.8 and 3.12).
- README badges and an illustrative animated demo.

### Fixed
- Documented `poppler` as a required system binary for the Tesseract OCR path
  (`pdf2image` fails without it).

[1.0.1]: https://github.com/leiverkus/rename-scientific-pdf/releases/tag/v1.0.1
[1.0.0]: https://github.com/leiverkus/rename-scientific-pdf/releases/tag/v1.0.0
