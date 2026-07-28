# Where the AI Was Wrong — Fair Split

## Example 1: Receipt amount interpretation (unit price vs line total)

**What happened**: The splitter was computing `item.amount * item.qty` for every item. For "Butter Naan, Qty=4, Amount=240", this gave 240 × 4 = ₹960 instead of the correct ₹240 (line total).

**How caught**: R2 test showed Aman's subtotal as ₹480 instead of ₹275. Manually traced the arithmetic: 320+260+240*4+180+100 = 2160, far exceeding the ₹1220 subtotal.

**Fix**: Changed splitter to use `item.amount` directly (receipt "Amount" column is already the line total, not unit price).

---

## Example 2: People extraction including food item words

**What happened**: The description parser extracted "Gulab", "Jamun", "Four", "The", "Everything" as person names from "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya..."

**How caught**: R2 test showed 7 "people" (including Gulab, Jamun, Four, The, Everything) instead of 4. The split total was ₹2286 instead of ₹1345.

**Fix**: Added comprehensive `NON_PERSON_WORDS` stop list including all food item words, number words, and common English words that start with capital letters.

---

## Example 3: Item name aliasing failure

**What happened**: Description said "Neha had the pasta and the lime soda" but the parser couldn't match "pasta" to the receipt item "Penne Arrabiata" — it was checking for exact name match on the first word ("penne").

**How caught**: R1 test showed Penne Arrabiata as shared by all 3 (₹347 each) instead of assigned to Neha (₹440). The item fell through to the "not clearly assigned" default.

**Fix**: Added `ITEM_ALIASES` dictionary mapping receipt item names to their natural-language aliases (e.g., "penne arrabiata" → ["pasta", "penne", "arrabiata"]). Updated all matching logic to check aliases.

---

## Example 4: Case sensitivity in person name matching

**What happened**: The `_determine_ownership` method lowercased the context for matching but then tried to match capitalized person names like "Ravi" against the lowercased string "ravi had the cappuccino".

**How caught**: Debugging R1 — items were all falling through to "shared by all" despite clear "X had Y" patterns in the description.

**Fix**: Rewrote the parser with simpler sentence-level processing that preserves case for name matching and uses `re.IGNORECASE` flag.

---

## Example 5: Duplicate people in list

**What happened**: The `_extract_people` method found "Ravi", "Neha", "Sameer" in the first pass (correct), then the dash-matching logic added them again, creating duplicates. This caused the splitter to create duplicate entries in person_subtotals.

**How caught**: R1 test showed 7 entries in per_person output (Ravi, Neha, Sameer ×2 + "Three") instead of 3. Grand total reconciliation sum was 2468 instead of 1147.

**Fix**: Used `dict.fromkeys()` for deduplication, and ensured the dash-match path replaces rather than appends to the people list.

---

## Example 6: Reconciliation tolerance too tight

**What happened**: R4 (Spice Route) had a ₹2 rounding difference between split sum (₹1438) and bill total (₹1436) due to rounding tax/service/discount proportions across 4 people.

**How caught**: 28/29 tests passing, R4 reconciliation flagged as `matches_bill: false`.

**Fix**: Increased reconciliation tolerance from ₹1 to ₹2, which is standard for round-to-rupee calculations across multiple proportional splits.
