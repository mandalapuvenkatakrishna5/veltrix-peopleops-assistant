# Design notes

## Ingestion, chunking and retrieval
`app/ingest.py` reads every manifest entry from `CORPUS_DIR`, dispatches by extension, extracts PDF text page-by-page, extracts DOCX paragraphs and tables, and parses HTML/Markdown. A page with no extractable PDF text is rendered and passed through Tesseract OCR; this handles the scanned memo without transcribing it by hand. Chunks are paragraph/heading-oriented with a character cap and overlap, and each chunk retains `doc_id`, region, effective date, access level, and a section/page locator. `app/retrieval.py` filters metadata before ranking and uses lexical overlap to avoid an external vector service. For 10,000 documents, lexical scans become slower and semantically weak; use local persisted BM25 plus an HNSW/FAISS vector index, incremental ingestion, and metadata prefilters.

## Policy rules
`eligible` in `app/retrieval.py` enforces access level, region, and effective date before text can be sent to the LLM. `rank_doc` / `resolve_precedence` implement authority, then regional specificity, then effective date. A production-grade next step is rule-aware retrieval that groups chunks by the rule being asked about, detects conflicting values, and explicitly reports unresolved ties and upcoming winning changes.

## Access control and personal data
Identity is loaded from SQLite in `app/main.py` using `X-Employee-Id`; user-supplied role or region is not trusted. Session ownership is checked in `app/orchestrator.py`. Leave permission checks are inside `app/tools.py`, not the prompt. Employee data queries use parameterized SQL. Logs record employee IDs only and corpus token counts, never names, email addresses, or phone numbers. Only the minimal identity fields needed for permissions are passed to the model. Personal data should be added to the prompt only for a request that needs it, with email masking before output.

## Failure modes and mitigations
The scanned PDF has no text layer, so ingestion uses OCR. Malformed or missing documents fail startup instead of silently serving incomplete content. Context selection caps corpus text below 3,000 tokens and records the count per LLM call. Leave writes use `BEGIN IMMEDIATE` and a transaction for request/balance updates. Further hardening needed before final submission: exhaustive holiday-format extraction, complete date phrase parsing, policy contradiction detection, robust email masking, persistent session/proposal state, and broader integration tests.
