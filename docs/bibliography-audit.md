# Bibliography audit

## Closed bibliography contract

The manuscript bibliography contains **60 scholarly records**, and the structural checker requires the set of 60 BibTeX keys to equal the set of cited keys. No entry may be uncited, no citation may be undefined, and every record must also appear in `bibliography-audit.csv` with a DOI, official proceedings URL, arXiv identifier, or canonical ISBN record. `paper/check_references.py` enforces this closed-set contract before every paper build.

The audit was refreshed through 2026-09-20 against primary publisher/proceedings pages, DOI records, arXiv records, or the canonical print-book ISBN. It corrected, upgraded, or completed 25 records. Material repairs included the published author lists for vAttention, FlexGen, SAFECode, and CHERI; the actual CC 2016 record for Low-Fat Pointers; published NeurIPS records for MInference, SnapKV, InfLLM, H2O, and Scissorhands; official MLSys records for Keyformer and FlashInfer; and official PMLR/USENIX/proceedings metadata for serving papers. The CSV records the action taken per key.

This is a metadata and citation-coverage audit, not a claim that every cited paper was a full-paper calibration read. The separate calibration matrix records **13 same-venue TACO + 5 influential/foundational + 7 adjacent full-paper reads**. Those 25 reads satisfy the writing-calibration requirement independently of the 60-entry relevance-first bibliography. A citation count alone is not evidence of breadth, novelty, or correctness.

## Reliability boundary

The build-time checker is intentionally offline. It proves consistency among the manuscript, BibTeX database, and audit ledger; it does not prove that an external publisher will keep a URL live or that a DOI registry can never change. The row-level verification URL and identifier preserve the exact record used for manual verification. No third-party paper PDF is included in the artifact.
