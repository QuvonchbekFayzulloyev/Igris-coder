---
name: academic-documentation
description: Governs academic and engineering documentation: research papers, technical reports, theses, datasheets, API docs, patent applications. Supports LaTeX, Markdown, and DOCX formats.
pipeline_stage: Execution
triggers: [document, paper, report, thesis, documentation, latex, academic, research, write, draft, citation, reference, abstract, introduction, methodology, conclusion, datasheet, manual, specification]
defers_to: []
used_by: [reprompt-loop, skill-loader]
---

## Scope
Applies when the user requests academic, technical, or engineering
documentation. Covers research papers, technical reports, theses,
datasheets, API documentation, and patent applications.

## Procedure
1. **Identify document type**: paper, report, thesis, datasheet, manual
2. **Determine format**: LaTeX (academic), Markdown (technical), DOCX (business)
3. **Structure**:
   - Research paper: Abstract → Introduction → Related Work → Methodology → Results → Discussion → Conclusion → References
   - Technical report: Executive Summary → Background → Design → Implementation → Testing → Results → Recommendations
   - Datasheet: Overview → Features → Electrical → Mechanical → Packaging → Ordering
4. **Citations**: use BibTeX for LaTeX, IEEE/APA/ACM format as requested
5. **Figures**: describe figure placement, captions, cross-references
6. **Tables**: proper formatting with captions and labels

## LaTeX Templates
- `templates/latex/paper.tex` - IEEE/conference paper
- `templates/latex/report.tex` - Technical report
- `templates/latex/thesis.tex` - Thesis/dissertation
- `templates/latex/datasheet.tex` - Component datasheet

## Citation Styles
- IEEE: [1], [2], [3] numbered
- APA: (Author, Year)
- ACM: superscript numbers
- Harvard: (Author Year)

## Document Quality Checklist
- [ ] All figures have captions and are referenced in text
- [ ] All tables have captions and are referenced in text
- [ ] All citations have corresponding references
- [ ] All acronyms are defined on first use
- [ ] Equations are numbered and referenced
- [ ] Abstract is <= 300 words (or specified limit)
- [ ] Keywords are included (5-7 terms)
- [ ] Page numbers are included
- [ ] Headers/footers are consistent

## Anti-patterns
- Submitting without proofreading for grammar and spelling
- Missing citations for technical claims
- Figures without captions or labels
- Inconsistent citation style throughout the document
- Not defining acronyms on first use
- Missing abstract or keywords
