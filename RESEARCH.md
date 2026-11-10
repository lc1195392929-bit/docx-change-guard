# Research notes — 2026-11-10

## Motivation and baseline

A local reproduction using python-docx 1.2.0 showed that assigning `Paragraph.text` collapses run formatting and removes a synthetic field; modifying a target run instead can retain untouched runs. Official test/source reading provided the test methodology, not copied implementation:
- https://github.com/python-openxml/python-docx/blob/master/tests/text/test_paragraph.py
- https://github.com/python-openxml/python-docx/blob/master/src/docx/text/paragraph.py

The broader research began with GitHub weekly/monthly trend leads around AI skills and security. Official Trending pages were not independently accessible in that research run; third-party snapshots were selection leads only, not verified rankings. This project is **not** described as a trending repository or a superior alternative to all existing products.

## Related work checked

- [Docxodus](https://github.com/JSv4/Docxodus): repository README describes much broader semantic diff, expected deltas, deliverable verification and rendering. Repository displays MIT license. This is substantial overlap, so we make no category novelty claim.
- [ooxml-integrity](https://github.com/Dmitry-Kov/ooxml-integrity): deterministic checks for OOXML integrity, including comment-anchor failures. Repository displays MIT license. Its broader correctness checks are not replaced by our gate.
- [docx-compare](https://github.com/DOCX-Compare/docx-compare): text-oriented DOCX comparison. We did not reuse its code and do not assert license suitability without a file-level review.
- [ooxml.js fidelity inventory issue](https://github.com/ExaDev/ooxml.js/issues/65): public problem inventory includes fields, bookmarks, comment anchors and revisions. This is evidence of a practical preservation problem, not proof that this tool solves every listed construct.

## Narrow contribution

A portable single-file, standard-library Python gate with reviewable exact attribute contracts tied to a baseline archive hash; unknown changes fail conservatively. It has no renderer, network dependency or wildcard approval. This is an engineering trade-off, not an absolute originality claim: existing sophisticated tools may cover these needs and more.

## What remains to investigate

Broader real-world public-document corpus, controlled Word/WPS round-trips, strict OOXML and additional encodings, smarter address stability, schema validation integration and process-level memory quotas. No publication claim about any private thesis, actual student data, or production app tests is made.
