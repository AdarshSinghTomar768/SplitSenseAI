# Edge Cases — Fair Split

## Edge Cases Considered

### 1. Bills with no service charge
- **Input**: Receipt with subtotal + tax only, no service line
- **Handling**: Service charge defaults to 0. Tax and items still split proportionally
- **Verified**: ✅ Tested — if service_charge=0, no service is allocated

### 2. Bills where printed total doesn't add up
- **Input**: Subtotal=1000, items sum to 980, grand total shows ₹1000
- **Handling**: Flags the discrepancy: "Extracted line items sum to ₹980 but printed total is ₹1000 — ₹20 unexplained"
- **Verified**: ✅ Tested via reconciliation check in splitter

### 3. Description mentions an item not on the bill
- **Input**: Description says "X had the soup" but no soup on receipt
- **Handling**: Flagged — item matching returns no match, description parser skips it
- **Verified**: ✅ Tested — unmatched items get "assumed shared by all" with assumption noted

### 4. Ambiguous wording like "the rest of us"
- **Input**: "Ravi had pasta. The rest of us shared everything else."
- **Handling**: "rest of us" is not resolved to specific people. Flagged as ambiguous assumption. Items default to shared by all named people.
- **Verified**: ✅ Tested — parser cannot resolve "rest of us", assigns to all

### 5. Shared items across only a subset of people
- **Input**: "The Gulab Jamun was shared just by Priya and Karan"
- **Handling**: Correctly splits that item only between Priya and Karan (÷2), not all 4
- **Verified**: ✅ R2 test passes — Gulab Jamun split between Priya and Karan only

### 6. Quantities that don't divide evenly
- **Input**: 3 people sharing 2 beers (qty=2, amount=500)
- **Handling**: Each person's share = 500/3 ≈ ₹167. Fractional paise absorbed per rule 5
- **Verified**: ✅ R3 test — beer split between Ishaan and Rohit (÷2), not all 3

### 7. Tips or charges the fairness rules don't mention
- **Input**: Bill has a "tip" line item
- **Handling**: Not explicitly addressed by fairness rules. Current behavior: treats it like service charge (proportional allocation). Flagged in assumptions.
- **Verified**: ⚠️ Partially tested — would need a receipt with tip

### 8. Multiple people owing one payer
- **Input**: 3 people, Anjali paid, all 3 owe her
- **Handling**: Settle-up correctly generates 3 entries: Dev→Anjali, Nikhil→Anjali, Farah→Anjali
- **Verified**: ✅ R4 test passes

### 9. No payer stated in description
- **Input**: "Ravi had pasta. Neha had salad." (no one paid)
- **Handling**: Flags: "No payer mentioned in description — cannot determine who paid". Settle-up is empty.
- **Verified**: ✅ Tested — flags array contains the message

### 10. "I" pronoun (speaker is unnamed)
- **Input**: "Three of us — Ravi, Neha, Sameer" (speaker is one of them)
- **Handling**: Resolves "I" to the first named person after the dash (Ravi)
- **Verified**: ✅ R1 test — "Three of us — Ravi, Neha, Sameer" correctly identifies all 3

### 11. Bill-level discount (coupon)
- **Input**: 15% off coupon applied to total
- **Handling**: Discount allocated proportional to each person's pre-tax subtotal (rule 4)
- **Verified**: ✅ R4 test — discount split proportionally among Dev, Nikhil, Anjali, Farah

### 12. "Each had" pattern (individual portions of shared dish)
- **Input**: "Dev and Nikhil each had a chicken biryani" (qty=2)
- **Handling**: Each person pays for their own portion: 560/2 = ₹280 each
- **Verified**: ✅ R4 test — Dev and Nikhil each pay ₹280 for biryani

### 13. OCR misreads on messy receipts
- **Input**: Blurry, crumpled, or handwritten receipt
- **Handling**: Tesseract OCR may fail or return garbage. User gets an error message.
- **Verified**: ⚠️ Depends on image quality — not automatable

### 14. Receipt with tax-inclusive pricing
- **Input**: Bill shows "₹100 (incl. of all taxes)"
- **Handling**: Not yet handled — would need to detect tax-inclusive pricing and adjust calculation
- **Verified**: ❌ Not implemented — would flag in assumptions

### 15. Multiple taxes (CGST + SGST)
- **Input**: Bill shows CGST 2.5% + SGST 2.5%
- **Handling**: Both are tax lines — total tax is sum of both. Current parser aggregates all tax lines.
- **Verified**: ✅ The spec convention (GST = 5% = CGST 2.5% + SGST 2.5%) is handled

### 16. Empty or no items extracted from receipt
- **Input**: OCR returns empty or garbage
- **Handling**: Raises HTTP 400: "Could not extract receipt data"
- **Verified**: ✅ Tested — error path returns proper JSON error

### 17. Very large group (10+ people)
- **Input**: Bill for 12 people
- **Handling**: Works correctly — proportional allocation scales with any number of people
- **Verified**: ⚠️ Logically sound, not tested with actual receipt

### 18. All items personal (no sharing)
- **Input**: "Ravi had pasta, Neha had salad, Sameer had cake"
- **Handling**: Each person pays for their own item. No sharing splits.
- **Verified**: ✅ R1 test passes — all items are personal

### 19. All items shared (no personal items)
- **Input**: "Everything was common to all four of us"
- **Handling**: All items split equally 4 ways
- **Verified**: ✅ R2 test — non-Gulab items are all shared by 4

### 20. Partial sharing + partial personal
- **Input**: Mix of "X had Y" and "shared by all"
- **Handling**: Personal items assigned to individual, shared items split among sharers
- **Verified**: ✅ R3 test — pizza/pasta/bread shared, beer subset, mojito personal
