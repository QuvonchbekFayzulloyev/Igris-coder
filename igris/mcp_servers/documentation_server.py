"""MCP surface for documentation generation and academic writing.

Provides tools for:
- LaTeX document generation (papers, reports, theses)
- Markdown to PDF/HTML conversion
- Diagram generation (Mermaid, PlantUML, GraphViz)
- Citation management (BibTeX)
- Document templates
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("documentation")

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

LATEX_PAPER_TEMPLATE = r"""\documentclass[10pt,conference]{IEEEtran}
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{hyperref}
\def\BibTeX{{\rm B\kern-.05em{\sc i\kern-.025em b}\kern-.08em
    T\kern-.1667em\lower.7ex\hbox{E}\kern-.125emX}}

\title{{{title}}}

\author{
\IEEEauthorblockN{{{authors}}}
\IEEEauthorblockA{{{affiliation}}}
}

\begin{document}

\maketitle

\begin{abstract}
{abstract}
\end{abstract}

\begin{IEEEkeywords}
{keywords}
\end{IEEEkeywords}

{body}

\bibliographystyle{IEEEtran}
\bibliography{references}

\end{document}"""

LATEX_REPORT_TEMPLATE = r"""\documentclass[11pt,a4paper]{report}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{geometry}
\geometry{margin=1in}

\title{{{title}}}
\author{{{authors}}}
\date{{\today}}

\begin{document}

\maketitle

\begin{abstract}
{abstract}
\end{abstract}

\tableofcontents
\newpage

{body}

\bibliographystyle{plain}
\bibliography{references}

\end{document}"""

LATEX_DATASHEET_TEMPLATE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{geometry}
\usepackage{multicol}
\geometry{margin=0.8in}

\title{{\huge {part_number} -- {title}}}
\author{{}}
\date{{\today}}

\begin{document}

\maketitle

\begin{multicols}{2}
\section*{Features}
{features}
\end{multicols}

\section*{Description}
{description}

\section*{Applications}
{applications}

\section*{Electrical Characteristics}
\begin{longtable}{lcc}
\toprule
\textbf{Parameter} & \textbf{Min} & \textbf{Max} \\ \midrule
{elec_params}
\bottomrule
\end{longtable}

\section*{Mechanical Dimensions}
{mechanical}

\section*{Pin Configuration}
{pin_config}

\section*{Ordering Information}
{ordering}

\end{document}"""

MARKDOWN_TEMPLATE = """# {title}

**Authors:** {authors}  
**Date:** {date}  
**Version:** {version}

## Abstract
{abstract}

## Keywords
{keywords}

{body}

## References
{references}
"""

MERMAID_DIAGRAM_TEMPLATE = """```mermaid
{diagram_type}
{direction}
{content}
```"""

PLANTUML_TEMPLATE = """@startuml
{content}
@enduml"""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_latex_document(
    doc_type: str,  # paper | report | thesis | datasheet
    title: str,
    authors: str,
    abstract: str = "",
    keywords: str = "",
    body: str = "",
    output_path: str = "",
) -> str:
    """Generate a LaTeX document from template.

    Args:
        doc_type: paper (IEEE), report, thesis, or datasheet
        title: document title
        authors: author names (comma-separated)
        abstract: abstract text
        keywords: comma-separated keywords
        body: LaTeX body content
        output_path: optional path to save .tex file

    Returns:
        Path to generated .tex file
    """
    templates = {
        "paper": LATEX_PAPER_TEMPLATE,
        "report": LATEX_REPORT_TEMPLATE,
        "thesis": LATEX_REPORT_TEMPLATE,
        "datasheet": LATEX_DATASHEET_TEMPLATE,
    }

    if doc_type not in templates:
        return f"ERROR: Unknown doc_type '{doc_type}'. Use: paper, report, thesis, datasheet"

    template = templates[doc_type]

    # Prepare template variables
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    kw_str = ", ".join(kw_list)

    if doc_type == "datasheet":
        content = template.format(
            part_number=title.split()[0] if title else "PART",
            title=title,
            features="• Feature 1\n• Feature 2\n• Feature 3",
            description="Device description here.",
            applications="• Application 1\n• Application 2",
            elec_params="Vcc & 3.0V & 3.6V \\\\\nTemp & -40°C & 85°C \\\\",
            mechanical="See mechanical drawing.",
            pin_config="See pinout table.",
            ordering="Part number: " + (title.split()[0] if title else "PART"),
        )
    else:
        affiliation = "University / Company"
        content = template.format(
            title=title,
            authors=authors,
            affiliation=affiliation,
            abstract=abstract,
            keywords=kw_str,
            body=body or r"\section{Introduction}\nContent here.",
        )

    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
        return f"SUCCESS: LaTeX document saved to {output_path}"
    else:
        return content


@mcp.tool()
async def compile_latex_to_pdf(
    tex_path: str,
    output_dir: str = "",
    clean_aux: bool = True,
) -> str:
    """Compile LaTeX to PDF using pdflatex.

    Args:
        tex_path: path to .tex file
        output_dir: output directory (default: same as tex)
        clean_aux: remove .aux, .log, .out files after compilation

    Returns:
        Path to generated PDF or error message
    """
    tex_file = Path(tex_path)
    if not tex_file.exists():
        return f"ERROR: File not found: {tex_path}"

    out_dir = Path(output_dir) if output_dir else tex_file.parent

    try:
        # Run pdflatex twice for references
        for i in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(out_dir), str(tex_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return f"ERROR: pdflatex failed:\n{result.stdout}\n{result.stderr}"

        pdf_path = out_dir / f"{tex_file.stem}.pdf"
        if not pdf_path.exists():
            return "ERROR: PDF not generated"

        if clean_aux:
            for ext in [".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".fls", ".fdb_latexmk"]:
                aux_file = out_dir / f"{tex_file.stem}{ext}"
                if aux_file.exists():
                    aux_file.unlink()

        return f"SUCCESS: PDF generated at {pdf_path}"

    except subprocess.TimeoutExpired:
        return "ERROR: Compilation timed out"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def generate_mermaid_diagram(
    diagram_type: str,  # graph, flowchart, sequence, class, state, er, gantt, pie, journey
    direction: str = "TD",  # TD, LR, TB, BT, RL
    nodes: list[dict] = None,
    edges: list[dict] = None,
    raw_content: str = "",
) -> str:
    """Generate a Mermaid diagram.

    Args:
        diagram_type: type of diagram
        direction: layout direction
        nodes: list of {id, label, shape} for auto-generation
        edges: list of {source, target, label} for auto-generation
        raw_content: complete mermaid content (overrides nodes/edges)

    Returns:
        Mermaid diagram code block
    """
    if raw_content:
        content = raw_content
    else:
        lines = [f"{direction}"]
        if nodes:
            for n in nodes:
                shape = n.get("shape", "")
                label = n.get("label", n["id"])
                if shape == "rect":
                    lines.append(f"    {n['id']}[{label}]")
                elif shape == "diamond":
                    lines.append(f"    {n['id']}{{{label}}}")
                elif shape == "circle":
                    lines.append(f"    {n['id']}(({label}))")
                else:
                    lines.append(f"    {n['id']}[{label}]")
        if edges:
            for e in edges:
                label = f"|{e['label']}|" if e.get("label") else ""
                lines.append(f"    {e['source']} -->{label} {e['target']}")
        content = "\n".join(lines)

    return MERMAID_DIAGRAM_TEMPLATE.format(
        diagram_type=diagram_type,
        direction=direction,
        content=content,
    )


@mcp.tool()
async def generate_plantuml_diagram(
    uml_type: str,  # class, sequence, usecase, state, activity, component, deployment
    content: str = "",
    participants: list[str] = None,
    classes: list[dict] = None,
) -> str:
    """Generate a PlantUML diagram.

    Args:
        uml_type: type of UML diagram
        content: raw PlantUML content
        participants: for sequence diagrams
        classes: for class diagrams [{name, attrs, methods, relationships}]

    Returns:
        PlantUML diagram code
    """
    if content:
        return PLANTUML_TEMPLATE.format(content=content)

    lines = [f"@start{uml_type}"]

    if participants:
        for p in participants:
            lines.append(f"participant {p}")

    if classes:
        for c in classes:
            lines.append(f"class {c['name']} {{")
            for attr in c.get("attrs", []):
                lines.append(f"    {attr}")
            for method in c.get("methods", []):
                lines.append(f"    {method}()")
            lines.append("}")
            for rel in c.get("relationships", []):
                lines.append(f"{c['name']} {rel['type']} {rel['target']}")

    lines.append("@end" + uml_type)
    return "\n".join(lines)


@mcp.tool()
async def create_bibtex_entry(
    entry_type: str,  # article, inproceedings, book, thesis, techreport, manual, misc
    cite_key: str,
    fields: dict,
) -> str:
    """Create a BibTeX entry.

    Args:
        entry_type: BibTeX entry type
        cite_key: citation key
        fields: dict with fields (author, title, journal, year, etc.)

    Returns:
        BibTeX entry string
    """
    required = {
        "article": ["author", "title", "journal", "year"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "book": ["author", "title", "publisher", "year"],
        "thesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "manual": ["title", "year"],
    }

    missing = [f for f in required.get(entry_type, []) if f not in fields]
    if missing:
        return f"ERROR: Missing required fields for {entry_type}: {missing}"

    lines = [f"@{entry_type}{{{cite_key},"]
    for key, value in fields.items():
        lines.append(f"  {key} = {{{value}}},")
    lines.append("}")

    return "\n".join(lines)


@mcp.tool()
async def markdown_to_pdf(
    markdown_path: str,
    output_path: str = "",
    css_path: str = "",
) -> str:
    """Convert Markdown to PDF using pandoc.

    Args:
        markdown_path: path to .md file
        output_path: output PDF path
        css_path: optional CSS for styling

    Returns:
        Path to generated PDF or error
    """
    md_file = Path(markdown_path)
    if not md_file.exists():
        return f"ERROR: File not found: {markdown_path}"

    out_file = Path(output_path) if output_path else md_file.with_suffix(".pdf")

    try:
        cmd = ["pandoc", str(md_file), "-o", str(out_file), "--pdf-engine=weasyprint"]
        if css_path:
            cmd.extend(["--css", css_path])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return f"ERROR: pandoc failed: {result.stderr}"

        return f"SUCCESS: PDF generated at {out_file}"

    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def get_document_template(
    template_name: str,
) -> str:
    """Get a document template.

    Args:
        template_name: template name

    Returns:
        Template content
    """
    templates = {
        "paper": LATEX_PAPER_TEMPLATE,
        "report": LATEX_REPORT_TEMPLATE,
        "thesis": LATEX_REPORT_TEMPLATE,
        "datasheet": LATEX_DATASHEET_TEMPLATE,
        "markdown": MARKDOWN_TEMPLATE,
    }

    if template_name not in templates:
        return f"ERROR: Unknown template '{template_name}'. Available: {list(templates.keys())}"

    return templates[template_name]


if __name__ == "__main__":
    mcp.run()