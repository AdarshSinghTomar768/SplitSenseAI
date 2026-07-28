# Prompt Log — Fair Split

## Architecture Decision: Extract structured data + compute in code

**Answer to the explicit question**: I chose to **extract structured data and compute the totals in code**, not let the model do the arithmetic.

**Why**: LLMs are unreliable at arithmetic — they hallucinate numbers, especially with rounding. The fairness rules require precise proportional allocation (tax, service, discount) and reconciliation. By extracting items/descriptions as structured data and doing all math in Python, we get deterministic, auditable results. The OCR/extraction step can use a model, but the splitting logic is pure code.

## Prompt/Design Iterations

| # | What Changed | Why |
|---|-------------|-----|
| 1 | Initial design: LLM does everything | Too unreliable for arithmetic — hallucinated totals |
| 2 | Split into OCR extraction + code computation | OCR extracts data, code does math — deterministic |
| 3 | Added pytesseract for receipt OCR | Free, local, no API key needed. Works for clean receipts |
| 4 | Rule-based description parser (regex) | Faster, cheaper, more predictable than LLM for structured parsing |
| 5 | Added item alias mapping | "pasta" must match "Penne Arrabiata" — needed alias dictionary |
| 6 | Fixed receipt amount interpretation | Receipt "Amount" column is line total, not unit price — stop multiplying by qty |
| 7 | Added reconciliation check | Self-audit: sum of splits must match bill total, flag discrepancies |
| 8 | Added edge case flags | Surface ambiguity instead of guessing — mandatory per spec |
| 9 | Removed LLM dependency entirely | No API key needed — works fully offline with Tesseract OCR |

## Trade-offs

- **Tesseract OCR** is free but less accurate than commercial OCR (GCP Vision, AWS Textract) for messy receipts
- **Regex-based description parsing** is fast but brittle — a vision LLM would handle natural language better
- **No persistence/auth** per spec — one bill in, one split out
- **Rounding tolerance of ₹2** prevents false reconciliation failures from rounding
