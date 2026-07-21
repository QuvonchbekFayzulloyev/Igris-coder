---
name: desktop-app-testing
description: Use when the user wants to test desktop applications, software UI, or verify visual design. Covers PyAutoGUI automation, OpenCV vision, OCR, PowerPoint/Word verification, screen capture, and design consistency checks.
pipeline_stage: Review
triggers: [test, desktop, app, ui, gui, screen, click, screenshot, vision, ocr, powerpoint, pptx, word, docx, design, layout, button, window, automation]
---

## Scope

Desktop application testing, design verification, and document inspection.
Uses real GUI automation (PyAutoGUI), computer vision (OpenCV), OCR (Tesseract),
and document analysis (python-pptx, python-docx).

## Tools

- `desktop_testing` MCP: screen capture, click/type/scroll, template matching,
  color checking, OCR, contour detection, drag/drop
- `document_testing` MCP: PPTX/DOCX inspection, design check, structure validation,
  text search, color palette analysis
- `browser` MCP: Web UI user journeys (alternative if testing a web app)
- `filesystem` MCP: save/find screenshots and test artifacts

## Procedures

### 1. Screen/UI element discovery
- Use `capture_screen` to get the current screen state
- Use `get_mouse_position` to find coordinates of elements
- Use `vision_find_contours` to detect buttons, boxes, input fields
- Use `ocr_read_text` to identify text labels on the screen

### 2. Click-based testing
- `desktop_click(x, y)` to click buttons
- `desktop_type(text)` to fill input fields
- `desktop_press("enter")` to submit forms
- `desktop_press("alt+f4")` to close windows
- Always capture a `before` and `after` screenshot

### 3. Visual regression testing
- Take a baseline screenshot of a known-good state
- After making changes, take another screenshot
- Use `vision_compare_images(baseline, new)` to get similarity %
- Investigate any differences above 5%

### 4. Template/icon matching
- Save reference images of buttons, icons, or logos
- Use `locate_on_screen(reference_image)` to find them
- Use `vision_match_template(screenshot, template)` for precise positioning

### 5. Color/design verification
- Use `pixel_color(x, y)` to check specific pixel values
- Use `pixel_matches_color(x, y, "#ff0000")` to verify brand colors
- Use `design_check_colors(screenshot)` to extract palette
- Use `design_check_layout(screenshot)` to verify alignment

### 6. PowerPoint testing
- Use `pptx_create_sample` to create test presentations
- Use `pptx_inspect` to verify slide content and structure
- Use `pptx_check_design` to check font/color consistency

### 7. Word document testing
- Use `docx_inspect` to check paragraphs, headings, tables
- Use `docx_check_structure` to verify heading hierarchy
- Use `docx_find_text` to verify specific content exists
- Use `ocr_read_text` on a rendered/printed version for visual check

### 8. OCR-based text verification
- Use `ocr_read_text(screenshot)` to extract all visible text
- Use `ocr_find_text(screenshot, "expected text")` for targeted search
- Use `ocr_regions(screenshot)` to get text positions for layout verification

## Anti-patterns
- Don't assume PyAutoGUI will find elements by image when the UI is scaled
  differently — always test with the actual screen resolution
- Tesseract must be installed separately (download from UB-Mannheim Tesseract wiki)
  for OCR to work; check with `tesseract --version` first
- PyAutoGUI fails on secure desktops (UAC prompts, login screens)
  because the OS blocks programmatic input to those windows
- Screenshots taken while a context menu is open may miss underlying elements
- When testing documents, verify both the file content (via python-pptx/docx)
  AND the visual rendering (via screenshot + OCR)
