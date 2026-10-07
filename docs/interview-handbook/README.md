# AetherFlow Technical Interview Handbook

This directory is the editable source for
[`docs/AetherFlow_Technical_Interview_Handbook.pdf`](../AetherFlow_Technical_Interview_Handbook.pdf).
The chapters are ordered by `build_pdf.py`; edit the Markdown files, then
rebuild the PDF.

## Build

Requirements: Python 3.12+ and a local Google Chrome or Microsoft Edge
installation in headless mode. The builder uses Python's standard library; it
does not add or install application dependencies.

From the repository root:

```powershell
python docs/interview-handbook/build_pdf.py
```

Optional text/link validation (requires the docs-only helper dependency):

```powershell
python -m pip install -r docs/interview-handbook/requirements-validation.txt
python docs/interview-handbook/validate_pdf.py
```

To render representative pages for visual inspection, pass one-based page
numbers and a temporary output directory, for example:

```powershell
python docs/interview-handbook/validate_pdf.py --render-pages 1,2,6,8,31,48 --render-dir $env:TEMP\aetherflow-handbook-pages
```

The script builds the HTML in a temporary directory, asks Chrome/Edge to print
it, verifies the resulting PDF signature and minimum size, and writes only the
target PDF. Use `--browser PATH` to select a non-default browser executable.

## Source layout

- `01-foundations.md`: chapters 1–5
- `02-queues-and-reliability.md`: chapters 6–10
- `03-application-engineering.md`: chapters 11–15
- `04-decisions-and-limits.md`: chapters 16–19
- `05-question-bank.md`: chapter 20 (24 interview categories)
- `06-mock-interviews.md`: chapters 21–23 (mock interviews, source navigation,
  glossary and revision sheets)

The builder supports normal headings, paragraphs, lists, tables, fenced code,
internal links, and the Mermaid `flowchart` and `sequenceDiagram` statements
used by these chapters. Diagrams render as vector SVG in the PDF.

## Claim discipline

The book was written against the current local source tree and its tests,
README, migrations, Compose configuration, ADRs, and testing report. Source
references are repository-relative. The working tree contains uncommitted
engineering-polish changes, including the current scheduled-job cancellation
behavior. The handbook distinguishes that current behavior from older ADR
text and from proposed future work. It does not claim personal incidents,
production traffic, a public deployment, exactly-once execution, or measured
performance.

Recheck implementation and run the validation commands in
`docs/TESTING.md` after substantive code changes; the verification date in the
PDF identifies one observed workspace run, not a guarantee about later code.
