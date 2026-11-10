# Validation record

Local validation on 2026-11-10, Python 3.12.14:

- `python -m unittest -v`: 29 tests passed.
- `python demo.py`: generated synthetic before/after packages and a hash-bound size-change contract; comparison passed.
- CLI exercised with exit 0 (no change), 1 (unexpected change), 2 (invalid input).
- Input bytes unchanged after comparison.

Tests cover exact size approvals, wrong expected values, stale hash, unused rules, text/citation superscript/field loss, added package relationships, changed binary media, comment/PI and namespace binding changes, conservative whitespace checks, attribute-order handling, DTD/UTF-16 rejection, nesting/node/entry/part limits, duplicate/path-traversal ZIP entries, unsupported compression and truncated reports failing closed.

An independent code-review pass reproduced namespace rebinding and root-level PI false negatives plus uncaught corrupt-DEFLATE errors. These were corrected and independently rechecked: all three regressions now reject or report structured error. Additional synthetic insertion of text, fields and hyperlinks failed as intended. The review also checked 129-level nesting and 200,001-element rejection. Comment and PI nodes now count during parsing as well.

This is bounded synthetic testing, not a proof of total correctness or a full security audit. No real-user documents were used. No Word/WPS rendering, official schema validation, deployed service, school-format rule or cross-platform compatibility certification was performed. Run your own local corpus and visual checks before relying on any automation.
