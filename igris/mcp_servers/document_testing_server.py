"""Document testing MCP server.

Provides tools for creating, inspecting, and verifying:
- PowerPoint (PPTX) files: slides, text, images, shapes, tables
- Word (DOCX) files: paragraphs, headings, tables, images, styles
- Design verification: layout, color schemes, fonts
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("document_testing")

# ---------------------------------------------------------------------------
# PowerPoint (PPTX) tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def pptx_inspect(file_path: str) -> str:
    """Inspect a PowerPoint file: list all slides with their content summary.

    Returns slide count, layout names, text content, and shape types.

    Args:
        file_path: path to the .pptx file
    """
    try:
        from pptx import Presentation
    except ImportError:
        return "ERROR: python-pptx not installed. Run: pip install python-pptx"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"
    if path.suffix.lower() not in (".pptx", ".pptm"):
        return f"ERROR: not a PowerPoint file: {path.suffix}"

    try:
        prs = Presentation(str(path))
        info = {
            "file": file_path,
            "slide_count": len(prs.slides),
            "slide_width": prs.slide_width,
            "slide_height": prs.slide_height,
            "slides": [],
        }

        for i, slide in enumerate(prs.slides, 1):
            slide_info = {
                "slide_number": i,
                "layout": slide.slide_layout.name if slide.slide_layout else "Unknown",
                "shapes": [],
            }
            for shape in slide.shapes:
                shape_info = {"name": shape.name, "type": str(shape.shape_type)}
                if shape.has_text_frame:
                    shape_info["text"] = shape.text_frame.text[:200]
                if shape.has_table:
                    rows = len(shape.table.rows)
                    cols = len(shape.table.columns)
                    shape_info["table"] = f"{rows}x{cols}"
                if hasattr(shape, "image"):
                    shape_info["image"] = True
                slide_info["shapes"].append(shape_info)

            info["slides"].append(slide_info)

        return json.dumps(info, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: failed to inspect PPTX: {e}"


@mcp.tool()
async def pptx_check_design(file_path: str) -> str:
    """Check PowerPoint design consistency: fonts, colors, layout usage.

    Args:
        file_path: path to the .pptx file
    """
    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError:
        return "ERROR: python-pptx not installed"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    try:
        prs = Presentation(str(path))
        report = {
            "file": file_path,
            "slide_count": len(prs.slides),
            "layouts_used": set(),
            "fonts": set(),
            "colors": set(),
            "issues": [],
        }

        for slide in prs.slides:
            if slide.slide_layout:
                report["layouts_used"].add(slide.slide_layout.name)
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        for run in para.runs:
                            if run.font.name:
                                report["fonts"].add(run.font.name)
                            if run.font.color and run.font.color.rgb:
                                report["colors"].add(str(run.font.color.rgb))
                            if run.font.size:
                                pt = run.font.size.pt if hasattr(run.font.size, "pt") else run.font.size / 12700
                                if pt and pt < 10:
                                    report["issues"].append(
                                        f"Small font ({pt:.0f}pt) in '{shape.name}': '{run.text[:50]}'"
                                    )

        report["layouts_used"] = sorted(report["layouts_used"])
        report["fonts"] = sorted(report["fonts"])
        report["colors"] = sorted(report["colors"])

        if len(report["layouts_used"]) > 5:
            report["issues"].append(f"Too many layouts: {len(report['layouts_used'])}")
        if len(report["fonts"]) > 3:
            report["issues"].append(f"Too many fonts: {len(report['fonts'])}")
        if len(report["colors"]) > 6:
            report["issues"].append(f"Too many colors: {len(report['colors'])}")

        return json.dumps(report, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: design check failed: {e}"


@mcp.tool()
async def pptx_create_sample(file_path: str, title: str = "Sample Presentation", slides: int = 3) -> str:
    """Create a sample PowerPoint file for testing.

    Args:
        file_path: output path for the .pptx file
        title: presentation title
        slides: number of slides to create
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
    except ImportError:
        return "ERROR: python-pptx not installed"

    try:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        for i in range(slides):
            slide_layout = prs.slide_layouts[1]  # Title and Content
            slide = prs.slides.add_slide(slide_layout)

            if slide.shapes.title:
                slide.shapes.title.text = f"{title} - Slide {i + 1}"

            if slide.placeholders:
                body = slide.placeholders[1]
                if body:
                    body.text = (
                        f"This is slide {i + 1} of the presentation.\n"
                        f"Content for testing purposes."
                    )

        prs.save(str(file_path))
        return f"Created: {file_path} ({slides} slides)"
    except Exception as e:
        return f"ERROR: create failed: {e}"


# ---------------------------------------------------------------------------
# Word (DOCX) tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def docx_inspect(file_path: str) -> str:
    """Inspect a Word document: paragraphs, headings, tables, images, styles.

    Args:
        file_path: path to the .docx file
    """
    try:
        from docx import Document
    except ImportError:
        return "ERROR: python-docx not installed. Run: pip install python-docx"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"
    if path.suffix.lower() not in (".docx", ".docm"):
        return f"ERROR: not a Word file: {path.suffix}"

    try:
        doc = Document(str(path))
        info = {
            "file": file_path,
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "sections": len(doc.sections),
            "headings": [],
            "content_preview": [],
            "styles_used": [],
            "images": 0,
        }

        style_names = set()
        for para in doc.paragraphs:
            if para.style:
                style_names.add(para.style.name)
            text = para.text.strip()
            if not text:
                continue
            if para.style and para.style.name.startswith("Heading"):
                info["headings"].append({"level": para.style.name, "text": text[:100]})

            if len(info["content_preview"]) < 20:
                info["content_preview"].append(text[:150])

        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                info["images"] += 1

        info["styles_used"] = sorted(style_names)
        return json.dumps(info, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: failed to inspect DOCX: {e}"


@mcp.tool()
async def docx_check_structure(file_path: str) -> str:
    """Check Word document structure: heading hierarchy, table of contents, formatting.

    Args:
        file_path: path to the .docx file
    """
    try:
        from docx import Document
    except ImportError:
        return "ERROR: python-docx not installed"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    try:
        doc = Document(str(path))
        issues = []
        headings = []
        prev_level = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style and para.style.name.startswith("Heading"):
                level = int(para.style.name.split()[-1])
                headings.append((level, text[:80]))
                if prev_level and level > prev_level + 1:
                    issues.append(
                        f"Heading jump: H{prev_level} -> H{level} ('{text[:50]}')"
                    )
                prev_level = level

        # Check heading sequence
        if headings:
            if headings[0][0] != 1:
                issues.append(f"Document does not start with H1 (starts with H{headings[0][0]})")
        else:
            issues.append("No headings found in document")

        # Check tables
        for i, table in enumerate(doc.tables):
            rows, cols = len(table.rows), len(table.columns)
            if rows == 0:
                issues.append(f"Table {i + 1}: empty (no rows)")

        report = {
            "file": file_path,
            "headings": headings,
            "issues": issues,
            "total_paragraphs": len(doc.paragraphs),
            "total_tables": len(doc.tables),
        }
        return json.dumps(report, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: structure check failed: {e}"


@mcp.tool()
async def docx_find_text(file_path: str, search_text: str) -> str:
    """Search for text in a Word document and return context.

    Args:
        file_path: path to the .docx file
        search_text: text to find
    """
    try:
        from docx import Document
    except ImportError:
        return "ERROR: python-docx not installed"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    try:
        doc = Document(str(path))
        matches = []
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if search_text.lower() in text.lower():
                ctx_start = max(0, i - 1)
                ctx_end = min(len(doc.paragraphs), i + 3)
                context_lines = []
                for j in range(ctx_start, ctx_end):
                    ptext = doc.paragraphs[j].text.strip()
                    prefix = ">>> " if j == i else "    "
                    if ptext:
                        context_lines.append(f"{prefix}{ptext[:150]}")
                matches.append({
                    "paragraph": i,
                    "context": "\n".join(context_lines),
                })

        if matches:
            return json.dumps(matches, indent=2, ensure_ascii=False)
        return f"Text '{search_text}' not found"
    except Exception as e:
        return f"ERROR: search failed: {e}"


# ---------------------------------------------------------------------------
# Design verification
# ---------------------------------------------------------------------------


@mcp.tool()
async def design_check_colors(file_path: str) -> str:
    """Extract and analyze the color palette from a screenshot or image.

    Args:
        file_path: path to an image file (PNG, JPG)
    """
    try:
        from PIL import Image
    except ImportError:
        return "ERROR: Pillow not installed. Run: pip install Pillow"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    try:
        img = Image.open(path).convert("RGB")
        pixels = img.getdata()

        # Count colors with a simple quantization
        color_map = {}
        for pixel in pixels:
            # Quantize to reduce colors
            q = tuple(v // 32 * 32 for v in pixel)
            color_map[q] = color_map.get(q, 0) + 1

        total = sum(color_map.values())
        sorted_colors = sorted(color_map.items(), key=lambda x: -x[1])

        dominant = []
        for color, count in sorted_colors[:10]:
            pct = count / total * 100
            hex_color = "#{:02x}{:02x}{:02x}".format(
                min(255, color[0] + 16),
                min(255, color[1] + 16),
                min(255, color[2] + 16),
            )
            dominant.append({"color": hex_color, "rgb": color, "percentage": round(pct, 1)})

        unique_colors = len(color_map)

        return json.dumps({
            "file": file_path,
            "image_size": f"{img.size[0]}x{img.size[1]}",
            "unique_colors_approx": unique_colors,
            "dominant_colors": dominant,
        }, indent=2)
    except Exception as e:
        return f"ERROR: color analysis failed: {e}"


@mcp.tool()
async def design_check_layout(file_path: str) -> str:
    """Analyze layout structure from a screenshot: detect regions, alignment.

    Args:
        file_path: path to an image file (screenshot)
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "ERROR: opencv-python not installed"

    path = Path(file_path)
    if not path.exists():
        return f"ERROR: file not found: {file_path}"

    try:
        img = cv2.imread(str(path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

        # Find content regions
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            if area > 500:  # Filter tiny noise
                regions.append({
                    "x": int(x), "y": int(y), "w": int(w), "h": int(h),
                    "area": int(area),
                    "center_x": int(x + w / 2),
                    "center_y": int(y + h / 2),
                })

        # Sort by position (top to bottom, left to right)
        regions.sort(key=lambda r: (r["y"], r["x"]))

        h_img, w_img = img.shape[:2]
        return json.dumps({
            "file": file_path,
            "image_size": f"{w_img}x{h_img}",
            "regions_found": len(regions),
            "regions": regions[:30],
        }, indent=2)
    except Exception as e:
        return f"ERROR: layout analysis failed: {e}"


if __name__ == "__main__":
    mcp.run()
