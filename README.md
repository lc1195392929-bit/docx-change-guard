# DOCX Change Guard

**A small local change-contract gate for automated DOCX formatting workflows.**

中文版：面向 AI 改格式的本地变更契约检查器。它不修改论文，不上传文件；比较修改前后 XML 与附件，只放行经过人工审查、绑定原文件哈希的精确属性变化。不是排版软件，也不代表论文格式达标。

## Why this exists

A formatter can change a font size correctly while accidentally losing a citation superscript, field, link, image or text. This CLI asks a narrower question than a visual diff: **did anything outside the reviewed attribute changes also change?** It defaults to deny, including harmless changes. It does not guess what was intended.

Python 3.10+; standard library only; no network requests or telemetry. Run from a downloaded/cloned repository:

```sh
python demo.py
python guard.py demo-output/before.docx demo-output/after.docx
# Exit 1: an unapproved size change exists.
python guard.py demo-output/before.docx demo-output/after.docx --contract demo-output/contract.json
# Exit 0: only the exact approved size attribute changed.
python -m unittest -v
```

The demo files are minimal **synthetic package fixtures**, not schema-complete Word templates. Use your local actual documents for additional tests; do not attach private theses to public issues.

## Exact contracts

A contract contains `version: 1`, the SHA-256 of the entire original archive (`before_sha256`) and `changes`. Every change has:

- `part`: exact package part, e.g. `word/document.xml`
- `path`: numeric XML child-index address, root `/0`, including in-tree comments/PIs
- `attribute`: expanded XML name, e.g. `{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val`
- `before` and `after`: exact strings, or `null` for absent attributes

Rules authorize **only attribute changes on existing same-tag nodes**, not inserted/deleted nodes, text, files, image data or namespace declarations. For a new font-size element, this version fails conservatively rather than silently approving a larger structural edit. There are no wildcard approvals. A stale baseline hash, incorrect expected value or unused approval prevents a pass. Review contracts independently: a tool cannot decide whether an explicitly approved change is desirable or safe.

The JSON report deliberately omits attribute values, document text and input filesystem paths. It includes package part names, XML names, node addresses and document hashes; **these may still reveal sensitive metadata**. Do not assume reports are anonymous. Contract files can contain sensitive values. Keep both local unless reviewed.

## What pass means (and does not mean)

`pass` means both inputs passed this tool's bounded input checks, all detected changes matched the supplied exact rules, all rules were used, and the report was not truncated. Without a contract, it means no detected modelled differences.

It is **not** an Open XML schema validator, malicious document scanner, content-quality judge, Word/WPS rendering test, digital-signature check or proof of universal preservation. Identical broken documents can pass. No external relationships are opened. Macros/binary attachments are compared as bytes, not executed or certified safe.

Comparison covers every part: XML expanded tags/attributes, text/tails, child order/count, comments, processing instructions, namespace declaration locations, plus exact binary content. It ignores ZIP timestamps, archive ordering/compression, XML declaration spelling and equivalent attribute ordering. XML indentation changes are deliberately reported, even when harmless. Namespace prefix renames also fail conservatively. Formatting inheritance is not computed: the underlying style XML is compared, but no rendered effect is inferred.

Supported: transitional WordprocessingML DOCX with internal package-root officeDocument relationship, UTF-8 or ASCII-compatible XML, STORE/DEFLATE compression. Strict OOXML, UTF-16 XML, DTD/entities, encrypted ZIP and other compression methods are rejected. Limits: 32 MiB archive, 64 MiB expanded total, 16 MiB per part, 2,048 entries, 200,000 XML nodes per part, depth 128; excessive compression ratios rejected. Reports cap at 2,000 changes and fail closed when truncated. This is a CLI, not a hardened multi-tenant upload service.

Exit codes: **0** contract satisfied, **1** unexpected changes/missing expected changes, **2** unsupported/invalid input. The CLI emits a generic error without parser snippets; inspect locally to diagnose. Document contents are never modified. Shell output redirection is your responsibility: do not redirect over an input document.

## Research and attribution

This is independently written, not a claim to have invented document fidelity checking. The design follows study of existing tools and publicly reproducible failure modes; see [RESEARCH.md](RESEARCH.md). No third-party project code or private user documents are bundled. MIT license.

## Validation scope

See [TESTING.md](TESTING.md). Tests use generated minimal fixtures; success is **not** evidence that Word/WPS visual output, school-specific formatting or a deployed application works. There is no hosted service, registration, payment, or upload endpoint.
