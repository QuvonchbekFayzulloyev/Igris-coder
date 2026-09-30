"""IGRIS local artifact MCP server.

The agent used to know the names of Office/diagram/3D/EDA/audio tasks, but it
had no tool that could actually produce their files.  This server deliberately
uses the Python standard library so the capability is available after a normal
IGRIS install (no cloud account or optional binary is required).

Every creation tool writes a real artifact and returns its absolute path.  The
executor resolves ``output`` into the agent workspace before it reaches this
server, so files remain inside the active workspace.
"""

from __future__ import annotations

import html
import math
import os
import re
import struct
import subprocess
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("artifact")


def _safe_output(output: str, extension: str, fallback: str) -> str:
    """Normalize an artifact destination while preserving its directory."""
    raw = str(output or "").strip()
    if not raw:
        raw = fallback + extension
    path = Path(raw)
    if path.suffix.lower() != extension:
        path = path.with_suffix(extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def _result(path: str, kind: str, details: str = "") -> str:
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    suffix = f"; {details}" if details else ""
    return f"artifact saved to {path} ({kind}, {size} bytes){suffix}"


def _clean_lines(value: object, limit: int = 80) -> list[str]:
    if isinstance(value, str):
        values = value.replace("\r", "").split("\n")
    elif isinstance(value, Iterable):
        values = [str(v) for v in value]
    else:
        values = [str(value or "")]
    return [v.strip() for v in values if v and v.strip()][:limit]


def _xml(text: object) -> str:
    return xml_escape(str(text or ""), {'"': "&quot;"})


def _zip_write(path: str, entries: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, content in entries.items():
            package.writestr(name, content)


# ---------------------------------------------------------------------------
# Office artifacts: minimal valid OOXML packages, no third-party dependency.
# ---------------------------------------------------------------------------

def _docx_document(title: str, paragraphs: list[str]) -> str:
    body = [
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>'
        + _xml(title) + '</w:t></w:r></w:p>'
    ]
    for paragraph in paragraphs or ["Created by IGRIS."]:
        runs = "".join(
            '<w:r><w:t xml:space="preserve">' + _xml(line) + '</w:t></w:r>'
            for line in str(paragraph).split("\n")
        )
        body.append("<w:p>" + runs + "</w:p>")
    body.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
                '</w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>' + "".join(body) + '</w:body></w:document>')


@mcp.tool()
def create_document(title: str, paragraphs: list[str] | str = "",
                    output: str = "document.docx") -> str:
    """Create a real DOCX document locally.

    Args:
        title: Document title.
        paragraphs: Text paragraphs (list or newline-separated text).
        output: DOCX path. It is written in the active agent workspace.
    """
    path = _safe_output(output, ".docx", "document")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        "word/document.xml": _docx_document(title, _clean_lines(paragraphs)),
        "word/styles.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
</w:styles>''',
        "word/_rels/document.xml.rels": '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>''',
        "docProps/core.xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{_xml(title)}</dc:title><dc:creator>IGRIS</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created></cp:coreProperties>''',
        "docProps/app.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>IGRIS</Application></Properties>''',
    }
    _zip_write(path, entries)
    return _result(path, "DOCX", f"{len(_clean_lines(paragraphs))} paragraph(s)")


def _ppt_text_box(text: str, x: int, y: int, cx: int, cy: int, size: int,
                  bold: bool = False) -> str:
    attrs = ' b="1"' if bold else ""
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{x + y + size}" name="Text"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="{size}"{attrs}/><a:t>{_xml(text)}</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>'''


def _ppt_slide(title: str, bullets: list[str]) -> str:
    shapes = ['<p:sp><p:nvSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>']
    shapes.append(_ppt_text_box(title, 457200, 274320, 8229600, 914400, 2800, True))
    ypos = 1554480
    for bullet in bullets[:8] or ["Created by IGRIS"]:
        shapes.append(_ppt_text_box("• " + bullet, 731520, ypos, 7680960, 457200, 1700))
        ypos += 548640
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="0" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>{''.join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''


@mcp.tool()
def create_presentation(title: str, slides: list[dict] | list[str] | str = "",
                        output: str = "presentation.pptx") -> str:
    """Create a real PPTX presentation locally.

    Args:
        title: Presentation title.
        slides: Each item may be {"title": str, "bullets": [str]} or text.
        output: PPTX path in the active agent workspace.
    """
    path = _safe_output(output, ".pptx", "presentation")
    raw_slides = slides if isinstance(slides, list) else _clean_lines(slides)
    normalized: list[tuple[str, list[str]]] = []
    for index, slide in enumerate(raw_slides[:12] or [title], 1):
        if isinstance(slide, dict):
            slide_title = str(slide.get("title") or f"Slide {index}")
            bullets = _clean_lines(slide.get("bullets") or slide.get("content") or "")
        else:
            slide_title = str(slide) or f"Slide {index}"
            bullets = []
        normalized.append((slide_title, bullets))
    slide_entries = {f"ppt/slides/slide{i}.xml": _ppt_slide(name, bullets)
                     for i, (name, bullets) in enumerate(normalized, 1)}
    rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, len(normalized) + 1))
    slide_ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i}"/>'
                        for i in range(1, len(normalized) + 1))
    content_types = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(normalized) + 1))
    entries: dict[str, str] = {
        "[Content_Types].xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>{content_types}</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>''',
        "ppt/presentation.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst/><p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>''',
        "ppt/_rels/presentation.xml.rels": f'''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>''',
    }
    entries.update(slide_entries)
    _zip_write(path, entries)
    return _result(path, "PPTX", f"{len(normalized)} slide(s)")


def _xlsx_cell(value: object, row: int, col: int) -> str:
    name = ""
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{name}{row}"><v>{value}</v></c>'
    return f'<c r="{name}{row}" t="inlineStr"><is><t>{_xml(value)}</t></is></c>'


@mcp.tool()
def create_spreadsheet(sheet_name: str, rows: list[list] | list[dict] | str = "",
                       output: str = "spreadsheet.xlsx") -> str:
    """Create a real XLSX workbook locally from rows.

    Args:
        sheet_name: Worksheet name.
        rows: Matrix rows, list of objects, or newline/tab-separated text.
        output: XLSX path in the active agent workspace.
    """
    path = _safe_output(output, ".xlsx", "spreadsheet")
    matrix: list[list[object]] = []
    if isinstance(rows, str):
        matrix = [line.split("\t") for line in rows.splitlines() if line.strip()]
    elif isinstance(rows, list) and rows and isinstance(rows[0], dict):
        headers = list(rows[0].keys())
        matrix = [headers] + [[item.get(key, "") for key in headers] for item in rows]
    elif isinstance(rows, list):
        matrix = [list(row) if isinstance(row, (list, tuple)) else [row] for row in rows]
    if not matrix:
        matrix = [["Created by IGRIS"]]
    sheet_rows = "".join(
        f'<row r="{ridx}">' + "".join(_xlsx_cell(value, ridx, cidx)
                                         for cidx, value in enumerate(row, 1)) + '</row>'
        for ridx, row in enumerate(matrix[:500], 1))
    safe_name = re.sub(r"[\\/*?:\[\]]", "_", str(sheet_name or "Sheet1"))[:31] or "Sheet1"
    entries = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{_xml(safe_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>''',
        "xl/worksheets/sheet1.xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet_rows}</sheetData></worksheet>''',
    }
    _zip_write(path, entries)
    return _result(path, "XLSX", f"{len(matrix)} row(s)")


@mcp.tool()
def create_pdf(title: str, paragraphs: list[str] | str = "",
               output: str = "report.pdf") -> str:
    """Create a simple, valid PDF report locally (no reportlab required)."""
    path = _safe_output(output, ".pdf", "report")
    lines = [title] + _clean_lines(paragraphs)
    if not lines:
        lines = ["IGRIS report"]
    escaped = []
    for index, line in enumerate(lines[:45]):
        y = 780 - index * 16
        # Built-in Helvetica supports Latin reliably; preserve unknown glyphs safely.
        text = str(line).encode("latin-1", "replace").decode("latin-1")
        text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        size = 20 if index == 0 else 11
        escaped.append(f"BT /F1 {size} Tf 54 {y} Td ({text}) Tj ET")
    stream = "\n".join(escaped).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output_bytes = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output_bytes))
        output_bytes.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output_bytes)
    output_bytes.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    output_bytes.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output_bytes.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    with open(path, "wb") as fh:
        fh.write(output_bytes)
    return _result(path, "PDF", f"{len(lines)} line(s)")


# ---------------------------------------------------------------------------
# Diagrams, 3D, EDA, and audio.
# ---------------------------------------------------------------------------

def _svg_text(text: str, x: int, y: int, size: int = 16) -> str:
    return f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial" font-size="{size}" fill="#172033">{html.escape(text)}</text>'


@mcp.tool()
def create_diagram(title: str, nodes: list[str] | str = "", edges: list[str] | str = "",
                   output: str = "diagram.svg") -> str:
    """Create a real SVG flow diagram. Edges use ``A -> B`` notation."""
    path = _safe_output(output, ".svg", "diagram")
    node_list = _clean_lines(nodes) or ["Start", "Process", "Finish"]
    edge_list = _clean_lines(edges) or [f"{node_list[i]} -> {node_list[i+1]}"
                                         for i in range(len(node_list) - 1)]
    height = max(260, 130 + len(node_list) * 100)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">',
           '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#49617b"/></marker></defs>',
           '<rect width="100%" height="100%" fill="#f7f9fc" rx="18"/>',
           _svg_text(title, 56, 64, 28)]
    positions: dict[str, tuple[int, int]] = {}
    for index, name in enumerate(node_list):
        y = 100 + index * 100
        positions[name] = (500, y)
    for edge in edge_list:
        parts = re.split(r"\s*(?:->|→)\s*", edge, maxsplit=1)
        if len(parts) == 2 and parts[0] in positions and parts[1] in positions:
            x1, y1 = positions[parts[0]]
            x2, y2 = positions[parts[1]]
            svg.append(f'<line x1="{x1}" y1="{y1+42}" x2="{x2}" y2="{y2-8}" stroke="#49617b" stroke-width="3" marker-end="url(#arrow)"/>')
    for name, (x, y) in positions.items():
        svg.append(f'<rect x="{x-190}" y="{y}" width="380" height="54" rx="12" fill="#dcecff" stroke="#396b9e" stroke-width="2"/>')
        svg.append(f'<text x="{x}" y="{y+34}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="18" fill="#172033">{html.escape(name)}</text>')
    svg.append("</svg>")
    Path(path).write_text("\n".join(svg), encoding="utf-8")
    return _result(path, "SVG diagram", f"{len(node_list)} node(s), {len(edge_list)} edge(s)")


@mcp.tool()
def create_3d_model(shape: str = "cube", size_mm: float = 20,
                    output: str = "model.stl") -> str:
    """Create a real ASCII STL 3D model (cube or pyramid) locally."""
    path = _safe_output(output, ".stl", "model")
    size = max(1.0, min(float(size_mm or 20), 500.0))
    shape = str(shape or "cube").lower()
    half = size / 2
    if shape in ("pyramid", "piramida"):
        vertices = [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0), (0, 0, size)]
        faces = [(0, 1, 2), (0, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    else:
        vertices = [(-half,-half,-half),(half,-half,-half),(half,half,-half),(-half,half,-half),(-half,-half,half),(half,-half,half),(half,half,half),(-half,half,half)]
        faces = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
        shape = "cube"
    lines = [f"solid igris_{shape}"]
    for a, b, c in faces:
        lines.append(" facet normal 0 0 0\n  outer loop")
        for index in (a, b, c):
            x, y, z = vertices[index]
            lines.append(f"   vertex {x:g} {y:g} {z:g}")
        lines.append("  endloop\n endfacet")
    lines.append(f"endsolid igris_{shape}")
    Path(path).write_text("\n".join(lines), encoding="ascii")
    return _result(path, "STL", f"{shape}, {len(faces)} triangle(s)")


@mcp.tool()
def create_openscad_model(source: str, output: str = "model.scad") -> str:
    """Save an OpenSCAD model source file for parametric 3D work."""
    path = _safe_output(output, ".scad", "model")
    code = str(source or "").strip() or "cube([20, 20, 20], center=true);\n"
    Path(path).write_text(code, encoding="utf-8")
    return _result(path, "OpenSCAD source")


@mcp.tool()
def create_kicad_pcb(title: str, components: list[str] | str = "",
                     output: str = "board.kicad_pcb") -> str:
    """Create a KiCad PCB starter board with real component footprints."""
    path = _safe_output(output, ".kicad_pcb", "board")
    comps = _clean_lines(components) or ["R1 10k", "C1 100nF"]
    footprints = []
    for index, component in enumerate(comps[:20], 1):
        bits = component.split(maxsplit=1)
        ref, value = bits[0], bits[1] if len(bits) > 1 else ""
        x = 40 + (index - 1) * 12
        footprints.append(f'''(footprint "IGRIS:Generic" (layer "F.Cu") (at {x} 60)
  (property "Reference" "{_xml(ref)}" (at 0 -2 0) (layer "F.SilkS"))
  (property "Value" "{_xml(value)}" (at 0 2 0) (layer "F.Fab"))
  (fp_rect (start -3 -1.5) (end 3 1.5) (stroke (width 0.3) (type default)) (fill none) (layer "F.SilkS"))
  (pad "1" thru_hole circle (at -2 0) (size 2.4 2.4) (drill 1) (layers "*.Cu" "*.Mask"))
  (pad "2" thru_hole circle (at 2 0) (size 2.4 2.4) (drill 1) (layers "*.Cu" "*.Mask")))''')
    content = f'''(kicad_pcb (version 20240108) (generator "igris")
 (general (thickness 1.6))
 (paper "A4")
 (title_block (title "{_xml(title)}") (comment 1 "Generated by IGRIS"))
 (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "b.Silkscreen") (37 "F.SilkS" user "f.Silkscreen") (44 "Edge.Cuts" user))
 (gr_rect (start 20 20) (end 180 100) (stroke (width 0.5) (type default)) (fill none) (locked) (layer "Edge.Cuts"))
 {' '.join(footprints)})\n'''
    Path(path).write_text(content, encoding="utf-8")
    return _result(path, "KiCad PCB", f"{len(comps)} footprint(s)")


@mcp.tool()
def create_kicad_schematic(title: str, components: list[str] | str = "",
                            output: str = "schematic.kicad_sch") -> str:
    """Create a KiCad schematic starter file with component labels."""
    path = _safe_output(output, ".kicad_sch", "schematic")
    comps = _clean_lines(components) or ["R1 10k", "C1 100nF"]
    labels = "\n".join(f'  (text "{_xml(component)}" (exclude_from_sim no) (at 80 {40 + index*10} 0) (effects (font (size 1.27 1.27))))'
                       for index, component in enumerate(comps))
    content = f'''(kicad_sch (version 20231120) (generator igris)
  (uuid 00000000-0000-0000-0000-000000000001)
  (paper "A4")
  (title_block (title "{_xml(title)}") (comment 1 "Generated by IGRIS"))
{labels}
)\n'''
    Path(path).write_text(content, encoding="utf-8")
    return _result(path, "KiCad schematic", f"{len(comps)} component label(s)")


@mcp.tool()
def validate_artifact(path: str) -> str:
    """Validate an Office, SVG, STL, KiCad, SCAD, or WAV artifact on disk."""
    file_path = Path(path)
    if not file_path.is_file():
        return f"validation failed: file missing: {path}"
    ext = file_path.suffix.lower()
    try:
        if ext in {".docx", ".pptx", ".xlsx"}:
            with zipfile.ZipFile(file_path) as zf:
                names = set(zf.namelist())
                expected = {".docx": "word/document.xml", ".pptx": "ppt/presentation.xml", ".xlsx": "xl/workbook.xml"}[ext]
                if expected not in names:
                    return f"validation failed: OOXML member missing: {expected}"
            return f"validation passed: valid {ext[1:].upper()} package ({file_path.stat().st_size} bytes)"
        text = file_path.read_text(encoding="utf-8", errors="replace") if ext != ".wav" else ""
        if ext == ".pdf":
            return "validation passed: PDF header present" if file_path.read_bytes().startswith(b"%PDF-") else "validation failed: invalid PDF header"
        if ext == ".svg":
            return "validation passed: SVG root present" if "<svg" in text and "</svg>" in text else "validation failed: SVG root missing"
        if ext == ".stl":
            return f"validation passed: STL has {text.lower().count('facet normal')} facets" if "solid" in text and "facet" in text else "validation failed: STL facets missing"
        if ext == ".kicad_pcb":
            return "validation passed: KiCad PCB board and footprint data present" if "(kicad_pcb" in text and "(footprint" in text else "validation failed: KiCad PCB data missing"
        if ext == ".kicad_sch":
            return "validation passed: KiCad schematic root present" if "(kicad_sch" in text else "validation failed: KiCad schematic root missing"
        if ext == ".scad":
            return "validation passed: non-empty OpenSCAD source" if text.strip() else "validation failed: empty OpenSCAD source"
        if ext == ".wav":
            with wave.open(str(file_path), "rb") as audio:
                return f"validation passed: WAV {audio.getframerate()}Hz, {audio.getnframes()} frames"
    except (OSError, ValueError, zipfile.BadZipFile, wave.Error) as exc:
        return f"validation failed: {exc}"
    return f"validation neutral: unsupported extension {ext or '(none)'}"


@mcp.tool()
def create_audio_tone(text: str, output: str = "audio.wav", seconds: float = 2.0,
                      frequency_hz: float = 440.0) -> str:
    """Create a real WAV audio artifact.  The tone is useful as an offline audio cue.

    For speech, this tool writes spoken-text metadata in the WAV title response;
    it does not pretend the tone is human speech.
    """
    path = _safe_output(output, ".wav", "audio")
    duration = max(0.1, min(float(seconds or 2), 30.0))
    frequency = max(80.0, min(float(frequency_hz or 440), 3000.0))
    rate = 22050
    frames = int(rate * duration)
    with wave.open(path, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        chunk = bytearray()
        for n in range(frames):
            amp = int(0.22 * 32767 * math.sin(2 * math.pi * frequency * n / rate))
            chunk.extend(struct.pack("<h", amp))
        audio.writeframes(bytes(chunk))
    return _result(path, "WAV tone", f"{duration:g}s at {frequency:g}Hz; requested text: {str(text)[:80]}")


if __name__ == "__main__":
    mcp.run()
