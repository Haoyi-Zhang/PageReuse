# TACO and template rule check

**Guide record:** 2026-09-20. **Current build and evidence update:** 2026-10-07. The latest author-guide retrieval was unavailable; this note does not certify a new full policy read or authorize submission.

## Current first-party findings

- TACO’s official author-guidelines search record states that the initial manuscript has a strict **20-page limit for text and figures, excluding references**, and that revised manuscripts may use 25 pages.
- The official guide requires **double-anonymous review** for ordinary submissions, with the stated exception for conference-extension papers.
- Supplementary material should include a short README describing the files and how to use them.
- TACO evaluates archival architecture/code-optimization contributions; mechanical format compliance does not establish scientific suitability.
- The current ACM class record is `acmart` **2.20 dated 2026-08-16**, under LPPL 1.3. The supplied `acmart.cls` declares the same version/date, and the supplied class and bibliography style are byte-identical to the copies used by the paper.
- ACM’s current authorship/AI policy must be checked again immediately before any external use. This internal draft already discloses that AI involvement was substantive in research design, proofs, code, synthetic data, execution, analysis, validation, writing, and self-audit.

Primary workflow sources:

- TACO author guidelines: https://dl.acm.org/journal/taco/author-guidelines
- ACM submission templates: https://www.acm.org/publications/authors/submissions
- ACM publications policies: https://www.acm.org/publications/policies
- Current `acmart` package record: https://ctan.org/pkg/acmart

The TACO full page intermittently returned HTTP 403 to automated retrieval; the official indexed record supplied the length and anonymity text. This limitation is recorded rather than replaced with a third-party rule page.

## Mechanical status of the current paper

- Class options: `acmsmall,screen,review,anonymous`.
- Visible author names, affiliations, acknowledgments, and identifying repository links: absent.
- Main sections: nine.
- Content length: exactly 20 pages before the bibliography.
- References: four additional pages; 60 cited scholarly entries. All 60 have row-level primary/canonical-record audit entries; 25 were corrected, upgraded, or completed during closeout.
- Physical class output: 486 × 720 points (6.75 × 10 inches). The class geometry is accepted as authoritative; no manual geometry change was made to force a colloquial “7×10” label.
- Publisher class, bibliography style, body font, margins, and spacing: unmodified.
- Figures: native TikZ/PGFPlots; tables: booktabs.
- Undefined citations/references and overfull boxes in the current isolated build: none. The native table and affected figure/model/evaluation pages have been viewed.
- No external manuscript submission or chair contact has been made. The companion repository is updated separately with the CPU sources and retained measurements.

## Scientific readiness status

The controlled C++ CPU allocator now realizes sequential boundaries, generation leases and masked byte loads; a written refinement connects it to the declared trace. Conformance covers 207 cases, with 200 retained optimum costs, 400 rejected controls and 741951 observed events. The 14-case paired campaign retains all 308 samples and directly measures setup, checking, allocation, adaptation, execution and the complete decoded-input path. Every complete-path case median regresses (certified/baseline 1.672--121.481). This closes the missing local realization and overhead measurement, not the separate questions of serving usefulness or TACO significance. Public serving traces, GPU execution, concurrent reclamation, numerical attention equivalence and deployment gains remain outside the evidence. Formatting and local conformance alone do not establish suitability or acceptance.

## Supplement description

The standalone `artifact/` directory is the only electronic supplement. `artifact/readme.txt` gives a short reviewer-facing description. It contains original code, generated inputs, retained results, written proofs, evidence ledgers, and reproduction commands; it contains no third-party paper PDFs, model weights, credentials, private data, or invented repository URL.
