#!/usr/bin/env python3
"""Build the editable AetherFlow handbook Markdown sources into a PDF."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent
OUTPUT = ROOT / "docs" / "AetherFlow_Technical_Interview_Handbook.pdf"
CHAPTER_FILES = [
    "01-foundations.md",
    "02-queues-and-reliability.md",
    "03-application-engineering.md",
    "04-decisions-and-limits.md",
    "05-question-bank.md",
    "06-mock-interviews.md",
]
FINAL_FILES: list[str] = []


def inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    links: list[str] = []

    def preserve_link(match: re.Match[str]) -> str:
        links.append(markdown_link(match))
        return f"__AETHERFLOW_LINK_{len(links) - 1}__"

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", preserve_link, escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)

    def repository_link(match: re.Match[str]) -> str:
        raw_path = html.unescape(match.group(1))
        candidate = ROOT.joinpath(*raw_path.replace("\\", "/").split("/"))
        if not candidate.is_file():
            return match.group(0)
        return f'<a href="{candidate.as_uri()}"><code>{raw_path}</code></a>'

    escaped = re.sub(
        r"<code>((?:backend|frontend|docs)/[^<]+|README\.md|docker-compose\.yml|\.env\.example)</code>",
        repository_link,
        escaped,
    )
    for index, link in enumerate(links):
        escaped = escaped.replace(f"__AETHERFLOW_LINK_{index}__", link)
    return escaped


def markdown_link(match: re.Match[str]) -> str:
    label = re.sub(r"`([^`]+)`", r"<code>\1</code>", match.group(1))
    label = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", label)
    target = html.unescape(match.group(2))
    if re.match(r"^https?://", target):
        href = target
    elif target.startswith("#"):
        href = target
    else:
        candidate = (SOURCE / target).resolve()
        href = candidate.as_uri() if candidate.is_file() else target
    return f'<a href="{html.escape(href, quote=True)}">{label}</a>'


def render_mermaid(source: str) -> str:
    """Render the handbook's deliberately small flowchart/sequence subset."""
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines or not (
        lines[0].startswith("flowchart") or lines[0] == "sequenceDiagram"
    ):
        raise ValueError("only flowchart and sequenceDiagram blocks are supported")
    if lines[0] == "sequenceDiagram":
        return render_sequence(lines[1:])
    direction = lines[0].split()
    if len(direction) > 2 or (len(direction) == 2 and direction[1] not in {"LR", "RL", "TD", "TB", "BT"}):
        raise ValueError(f"unsupported flowchart direction: {' '.join(direction[1:])}")
    return render_flowchart(lines[1:])


def _svg_text(
    text: str,
    x: int,
    y: int,
    *,
    anchor: str = "middle",
    class_name: str = "node-label",
) -> str:
    content = html.escape(text[:42] + "..." if len(text) > 42 else text)
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'class="{class_name}">{content}</text>'
    )


def render_flowchart(lines: list[str]) -> str:
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []

    def parse_node(token: str) -> str:
        token = token.strip()
        match = re.fullmatch(
            r"([A-Za-z0-9_]+)(?:\[\((.+)\)\]|\[(.+)\]|\((.+)\))?",
            token,
        )
        if not match:
            raise ValueError(f"unsupported flowchart node: {token}")
        identifier = match.group(1)
        label = match.group(2) or match.group(3) or match.group(4) or identifier
        nodes[identifier] = label
        return identifier

    for line in lines:
        match = re.fullmatch(
            r"(.+?)\s*-->\s*(?:\|([^|]*)\|\s*)?(.+)",
            line,
        )
        if match:
            source = parse_node(match.group(1))
            target = parse_node(match.group(3))
            edges.append((source, target, match.group(2) or ""))
        else:
            parse_node(line)
    if not nodes:
        raise ValueError("empty flowchart")
    order = list(nodes)
    width = 720
    cols = min(4, len(order))
    rows = (len(order) + cols - 1) // cols
    gap_x = 18
    gap_y = 45
    box_w = min(160, (width - 36 - gap_x * (cols - 1)) // cols)
    box_h = 48
    height = 46 + rows * (box_h + gap_y)
    positions = {
        name: (
            18 + (index % cols) * (box_w + gap_x),
            24 + (index // cols) * (box_h + gap_y),
        )
        for index, name in enumerate(order)
    }
    context_nodes = {
        "Browser", "Web", "API", "PG", "Redis", "Pub",
        "Kafka", "Worker", "Scheduler", "Provider", "Mock", "LLM",
    }
    if context_nodes.issubset(nodes):
        box_w = 190
        box_h = 48
        height = 370
        positions = {
            "Browser": (15, 22),
            "Web": (265, 22),
            "API": (515, 22),
            "Redis": (15, 102),
            "Pub": (265, 102),
            "PG": (515, 102),
            "Scheduler": (15, 182),
            "Kafka": (265, 182),
            "Worker": (515, 182),
            "Mock": (15, 262),
            "Provider": (265, 262),
            "LLM": (515, 262),
        }
    state_nodes = {
        "ACCEPTED", "QUEUED", "RUNNING", "CANCEL_REQUESTED", "CANCELLED",
        "SUCCEEDED", "FAILED", "RETRY", "DEAD_LETTERED",
    }
    if state_nodes.issubset(nodes):
        box_w = 190
        box_h = 48
        height = 420
        positions = {
            "CANCEL_REQUESTED": (15, 182),
            "CANCELLED": (15, 262),
            "ACCEPTED": (265, 22),
            "QUEUED": (265, 102),
            "RUNNING": (265, 182),
            "SUCCEEDED": (265, 262),
            "RETRY": (515, 182),
            "DEAD_LETTERED": (515, 102),
            "FAILED": (515, 262),
        }
    else:
        state_nodes = set()
    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Architecture flow diagram">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" '
        'refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" '
        'fill="#65758b"/></marker></defs>',
    ]
    for source_id, target_id, label in edges:
        x1, y1 = positions[source_id]
        x2, y2 = positions[target_id]
        source_x, source_y = x1 + box_w // 2, y1 + box_h // 2
        target_x, target_y = x2 + box_w // 2, y2 + box_h // 2
        dx, dy = target_x - source_x, target_y - source_y
        scale_x = (box_w / 2) / abs(dx) if dx else float("inf")
        scale_y = (box_h / 2) / abs(dy) if dy else float("inf")
        source_scale = min(scale_x, scale_y)
        target_scale = min(scale_x, scale_y)
        sx = source_x + round(dx * source_scale)
        sy = source_y + round(dy * source_scale)
        tx = target_x - round(dx * target_scale)
        ty = target_y - round(dy * target_scale)
        output.append(
            f'<path d="M{sx} {sy} Q{(sx + tx) // 2} {(sy + ty) // 2 - 10} {tx} {ty}" '
            'fill="none" stroke="#65758b" stroke-width="2" '
            'marker-end="url(#arrow)"/>'
        )
        if label and not context_nodes:
            output.append(
                _svg_text(
                    label,
                    (sx + tx) // 2,
                    (sy + ty) // 2 - 9,
                    class_name="edge-label",
                )
            )
    for name in order:
        x, y = positions[name]
        output.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" '
            'fill="#142131" stroke="#415873" stroke-width="1.5"/>'
        )
        wrapped = textwrap.wrap(nodes[name], width=max(12, box_w // 7)) or [nodes[name]]
        if len(wrapped) > 2:
            wrapped = [wrapped[0], wrapped[1][: max(10, box_w // 7 - 3)] + "..."]
        line_count = len(wrapped)
        baseline = y + box_h // 2 + 4 - (line_count - 1) * 6
        for line_index, label_line in enumerate(wrapped):
            output.append(
                _svg_text(
                    label_line,
                    x + box_w // 2,
                    baseline + line_index * 12,
                )
            )
    output.append("</svg>")
    return "".join(output)


def render_sequence(lines: list[str]) -> str:
    participants: list[tuple[str, str]] = []
    messages: list[tuple[str, str, str]] = []
    for line in lines:
        participant = re.fullmatch(r"participant\s+(\w+)\s+as\s+(.+)", line)
        message = re.fullmatch(r"(\w+)-+>{1,2}(\w+):\s*(.+)", line)
        if participant:
            participants.append((participant.group(1), participant.group(2)))
        elif message:
            messages.append((message.group(1), message.group(2), message.group(3)))
        elif line.startswith("Note over "):
            continue
        else:
            raise ValueError(f"unsupported sequence statement: {line}")
    if not participants or not messages:
        raise ValueError("sequence diagram needs participants and messages")
    width = 720
    top = 48
    row_h = 43
    height = top + 72 + row_h * len(messages) + 28
    centers = {
        identifier: 70 + index * (width - 140) // max(1, len(participants) - 1)
        for index, (identifier, _) in enumerate(participants)
    }
    result = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Sequence diagram">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" '
        'refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" '
        'fill="#62b6a1"/></marker></defs>',
    ]
    for identifier, label in participants:
        x = centers[identifier]
        result.append(
            f'<rect x="{x - 52}" y="12" width="104" height="34" rx="6" '
            'fill="#142131" stroke="#415873"/>'
        )
        result.append(_svg_text(label, x, 34))
        result.append(
            f'<path d="M{x} 46 V{height - 12}" stroke="#77889d" '
            'stroke-dasharray="4 4"/>'
        )
    for index, (source, target, label) in enumerate(messages):
        y = top + 64 + index * row_h
        result.append(
            f'<path d="M{centers[source]} {y} H{centers[target]}" '
            'stroke="#62b6a1" stroke-width="1.7" marker-end="url(#arrow)"/>'
        )
        result.append(
            _svg_text(label, width // 2, y - 6, class_name="edge-label")
        )
    result.append("</svg>")
    return "".join(result)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    in_code = False
    code: list[str] = []
    list_type: str | None = None
    table_rows: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    def flush_table() -> None:
        if not table_rows:
            return
        out.append("<table><thead><tr>")
        for cell in table_rows[0]:
            out.append(f"<th>{inline_markup(cell)}</th>")
        out.append("</tr></thead><tbody>")
        for row in table_rows[1:]:
            out.append("<tr>")
            for cell in row:
                out.append(f"<td>{inline_markup(cell)}</td>")
            out.append("</tr>")
        out.append("</tbody></table>")
        table_rows.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "```mermaid":
            flush_paragraph()
            flush_list()
            flush_table()
            diagram: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                diagram.append(lines[index])
                index += 1
            try:
                out.append(
                    f'<figure class="diagram">{render_mermaid(chr(10).join(diagram))}</figure>'
                )
            except ValueError as error:
                raise ValueError(f"Mermaid block at line {index}: {error}") from error
            index += 1
            continue
        if line.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
                code.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            flush_list()
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                index += 1
                continue
            table_rows.append(cells)
            index += 1
            continue
        flush_table()
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            title = heading.group(2)
            anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            out.append(
                f'<h{level} id="{anchor}">{inline_markup(title)}</h{level}>'
            )
            index += 1
            continue
        if line.startswith(">"):
            flush_paragraph()
            flush_list()
            quote: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quote.append(lines[index].lstrip("> ").strip())
                index += 1
            out.append(f"<blockquote><p>{inline_markup(' '.join(quote))}</p></blockquote>")
            continue
        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            current_type = "ul" if unordered else "ol"
            if list_type != current_type:
                flush_list()
                list_type = current_type
                out.append(f"<{list_type}>")
            item = (unordered or ordered).group(1)  # type: ignore[union-attr]
            checked = re.match(r"^\[([ xX])\]\s*(.*)$", item)
            if checked:
                mark = "☑" if checked.group(1).strip() else "☐"
                item = f"{mark} {checked.group(2)}"
            out.append(f"<li>{inline_markup(item)}</li>")
            index += 1
            continue
        if line.strip() == "---":
            flush_paragraph()
            flush_list()
            out.append("<hr/>")
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            index += 1
            continue
        paragraph.append(line.strip())
        index += 1
    flush_paragraph()
    flush_list()
    flush_table()
    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
    return "\n".join(out)


def find_browser(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else []
    candidates.extend(
        [
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for name in ("chrome", "msedge", "google-chrome", "chromium"):
        located = shutil.which(name)
        if located:
            return Path(located)
    raise RuntimeError("Chrome or Edge was not found; pass --browser PATH.")


def build(browser: Path, output: Path) -> None:
    chapters = []
    for filename in CHAPTER_FILES + FINAL_FILES:
        path = SOURCE / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing handbook source: {path}")
        chapters.append((filename, path.read_text(encoding="utf-8")))

    toc = ["<section class='toc'><h1>Contents</h1><ol>"]
    for filename, content in chapters:
        titles = re.findall(r"^# (.+)$", content, re.MULTILINE)
        if not titles:
            titles = [filename]
        for title in titles:
            anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            toc.append(f'<li><a href="#{anchor}">{inline_markup(title)}</a></li>')
    toc.append("</ol></section>")
    body = "\n".join(markdown_to_html(content) for _, content in chapters)
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AetherFlow Technical Interview Handbook</title>
<style>
@page {{ size: A4; margin: 18mm 17mm 19mm;
  @top-left {{ content: "AETHERFLOW  /  TECHNICAL HANDBOOK"; font: 8pt Arial,sans-serif; color:#607087; }}
  @bottom-left {{ content: "Source-grounded interview preparation"; font: 8pt Arial,sans-serif; color:#607087; }}
  @bottom-right {{ content: counter(page); font: 9pt Arial,sans-serif; color:#23364b; }}
}}
@page:first {{ @top-left {{ content:none; }} @bottom-left {{ content:none; }}
  @bottom-right {{ content:none; }} }}
* {{ box-sizing:border-box; }}
body {{ font-family:Arial,"Segoe UI",sans-serif; font-size:9pt; line-height:1.43; color:#172538; }}
h1,h2,h3 {{ color:#102238; line-height:1.18; break-after:avoid; }}
h1 {{ font-size:23pt; margin:0 0 14pt; padding-bottom:7pt; border-bottom:2pt solid #62b6a1; }}
h2 {{ font-size:15pt; margin:17pt 0 7pt; }}
h3 {{ font-size:11pt; margin:12pt 0 5pt; }}
p {{ margin:4pt 0 7pt; orphans:3; widows:3; }}
ul,ol {{ margin:3pt 0 9pt; padding-left:19pt; }}
li {{ margin:2.5pt 0; }}
strong {{ color:#102238; }}
code {{ font-family:Consolas,"Courier New",monospace; font-size:8pt; color:#225d53; }}
pre {{ background:#101c2b; color:#e4edf6; padding:9pt; border-radius:5pt;
  font:7.2pt/1.38 Consolas,"Courier New",monospace; white-space:pre-wrap;
  overflow-wrap:anywhere; break-inside:avoid; }}
pre code {{ color:inherit; font-size:inherit; }}
table {{ width:100%; border-collapse:collapse; margin:7pt 0 11pt; font-size:7.5pt;
  line-height:1.3; table-layout:auto; }}
thead {{ display:table-header-group; }}
th {{ background:#142131; color:white; text-align:left; font-weight:bold; }}
th,td {{ border:0.5pt solid #c5cfdb; padding:4pt 5pt; vertical-align:top; overflow-wrap:anywhere; }}
th:first-child,td:first-child {{ min-width:90px; }}
tr {{ break-inside:avoid; }}
blockquote {{ margin:8pt 0; padding:5pt 10pt; background:#edf4f5;
  border-left:3pt solid #62b6a1; break-inside:avoid; }}
blockquote p {{ margin:0; }}
hr {{ border:0; border-top:1pt solid #d5dce5; margin:12pt 0; }}
a {{ color:#176e64; text-decoration:none; }}
.toc {{ break-after:page; }}
.cover {{ break-after:page; }}
.toc h1 {{ margin-top:12pt; }}
.toc ol {{ padding-left:20pt; }}
.toc li {{ padding:3pt 0; }}
.diagram {{ margin:8pt 0 13pt; break-inside:avoid; }}
.diagram svg {{ display:block; width:100%; max-height:190pt; }}
.node-label {{ font:10px Arial,sans-serif; fill:#e6eff8; }}
.edge-label {{ font:9px Arial,sans-serif; fill:#334155; stroke:#fff; stroke-width:4px; paint-order:stroke; }}
h1[id^="chapter"] {{ break-before:page; }}
</style></head><body>
<section class="cover"><p style="color:#398b7b;font-weight:bold;letter-spacing:2px">AETHERFLOW</p>
<h1 style="font-size:34pt;border:0;margin:35mm 0 9pt">Technical Interview Handbook</h1>
<h2 style="font-size:17pt;color:#52667e">Distributed AI Job Orchestration Platform</h2>
<p>Architecture, reliability, source navigation, and FAANG-style interview preparation</p>
<p style="margin-top:22mm;color:#607087">Source-verified against the local repository snapshot · 2026-10-07</p>
<p style="color:#607087">Editable chapter source accompanies this PDF in <code>docs/interview-handbook/</code>.</p>
</section>
{''.join(toc)}
{body}
</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aetherflow-handbook-") as temp:
        html_path = Path(temp) / "handbook.html"
        pdf_path = Path(temp) / "handbook.pdf"
        html_path.write_text(html_doc, encoding="utf-8")
        command = [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={Path(temp) / 'profile'}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if completed.returncode != 0:
            raise RuntimeError(
                "Browser PDF generation failed:\n"
                + completed.stdout[-3000:]
                + completed.stderr[-3000:]
            )
        if not pdf_path.is_file() or pdf_path.stat().st_size < 20_000:
            raise RuntimeError("PDF generation produced a missing or implausibly small file.")
        with pdf_path.open("rb") as generated:
            if generated.read(5) != b"%PDF-":
                raise RuntimeError("Browser output does not have a valid PDF signature.")
        shutil.copyfile(pdf_path, output)
    print(f"Generated {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Chrome or Edge executable path")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    browser = find_browser(args.browser)
    build(browser, args.output.resolve())


if __name__ == "__main__":
    main()
