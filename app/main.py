import base64
import io
import json
import os
import re
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import SplitRequest, SplitResponse, ReceiptData, ReceiptItem
from .receipt_parser import extract_receipt_from_image, extract_items_from_image, parse_receipt_text
from .description_parser import DescriptionParser
from .splitter import BillSplitter

app = FastAPI(title="Fair Split API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = DescriptionParser()
splitter = BillSplitter()


def parse_description_text(description: str) -> dict:
    """Parse description to extract structured info without LLM."""
    people = []
    paid_by = None
    common_words = {
        'i', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours',
        'the', 'a', 'an', 'and', 'or', 'but', 'had', 'has',
        'have', 'was', 'were', 'is', 'are', 'just', 'shared',
        'common', 'everything', 'else', 'rest', 'of', 'us',
        'who', 'paid', 'bill', 'skipped', 'drinks', 'only',
        'both', 'three', 'four', 'two', 'one', 'none', 'all',
        'some', 'every', 'others', 'remaining', 'used', 'coupon',
        'off', 'were', 'each', 'was', 'skipped', 'things', 'item',
        'items', 'food', 'order', 'total', 'pay', 'split', 'owe',
        'owed', 'dish', 'dishes', 'meal', 'meals', 'portion',
        'included', 'excluding', 'except', 'besides', 'also',
        'too', 'with', 'without', 'between', 'among', 'amongst',
    }

    name_pattern = r'\b([A-Z][a-z]+)\b'
    found_names = re.findall(name_pattern, description)

    seen = set()
    for name in found_names:
        if name.lower() not in common_words and name not in seen:
            people.append(name)
            seen.add(name)

    paid_patterns = [
        (r'([A-Z][a-z]+)\s+paid', 1),
        (r'paid\s+by\s+([A-Z][a-z]+)', 1),
        (r'([A-Z][a-z]+)\s+footed', 1),
        (r'([A-Z][a-z]+)\s+picked\s+up', 1),
        (r'([A-Z][a-z]+)\s+covered', 1),
    ]
    for pattern, group in paid_patterns:
        m = re.search(pattern, description)
        if m:
            paid_by = m.group(group)
            break

    if not paid_by and re.search(r'\bI\s+paid\b', description):
        paid_by = "I"

    return {
        "people": people,
        "paid_by": paid_by,
    }


def parse_receipt_for_api(image_bytes: bytes) -> tuple:
    """Parse receipt with fallback approaches."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
    except Exception:
        text = ""

    items = []
    subtotal = 0.0
    service_charge = 0.0
    discount = 0.0
    tax = 0.0
    grand_total = 0.0

    if text:
        items = _extract_items_from_text(text)
        subtotal, service_charge, discount, tax, grand_total, _ = _extract_totals_from_text(text)

    if not items and subtotal == 0:
        raise ValueError("Could not extract receipt data. Please try a clearer image.")

    if subtotal == 0 and items:
        subtotal = sum(i.amount * i.qty for i in items)

    if grand_total == 0:
        grand_total = subtotal + service_charge - discount + tax

    return items, subtotal, service_charge, discount, tax, grand_total


def _extract_items_from_text(text: str) -> List[ReceiptItem]:
    """Extract items from receipt OCR text."""
    lines = text.strip().split('\n')
    items = []

    skip_keywords = [
        'subtotal', 'sub total', 'service', 'gst', 'tax', 'discount',
        'round', 'total', 'bill', 'grand', 'coupon', 'cgst', 'sgst',
        'amount', 'qty', 'item', 'price', 'date', 'time', 'table',
        'welcome', 'thank', 'copy', 'phone', 'inr', '₹',
        'ref', 'auth', 'card', 'cash', 'change', 'tip', 'server',
        'gstin', 'pan', 'invoice', 'print', 'counter', 'order',
        'welcome15', 'wELCOME15',
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        low = line.lower()
        if any(kw in low for kw in skip_keywords):
            continue

        patterns = [
            r'^(.+?)\s+(\d+)\s+(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
            r'^(.+?)\s+₹?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
            r'^(.+?)\s+(\d+)\s+pc\s+(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
            r'^(\D+?)\s+(\d+)\s+(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
        ]

        for pi, pattern in enumerate(patterns):
            m = re.match(pattern, line)
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    name = groups[0].strip()
                    try:
                        qty = int(groups[1])
                        amount = float(groups[2].replace(',', ''))
                    except ValueError:
                        continue
                elif len(groups) == 2:
                    name = groups[0].strip()
                    qty = 1
                    try:
                        amount = float(groups[1].replace(',', ''))
                    except ValueError:
                        continue
                else:
                    continue

                if name and amount > 0 and len(name) > 1 and qty > 0:
                    items.append(ReceiptItem(name=name, qty=qty, amount=amount))
                break

    return items


def _extract_totals_from_text(text: str) -> tuple:
    """Extract subtotal, service, discount, tax, grand total from text."""
    lines = text.strip().split('\n')
    subtotal = 0.0
    service_charge = 0.0
    discount = 0.0
    tax = 0.0
    grand_total = 0.0
    round_off = 0.0

    for line in lines:
        low = line.lower().strip()

        if 'subtotal' in low or 'sub total' in low or 'sub-total' in low:
            val = _parse_money_from_line(line)
            if val is not None:
                subtotal = val

        if ('service' in low and ('chrg' in low or 'charge' in low)) or \
           (re.search(r'service\s+\d', low)):
            val = _parse_money_from_line(line)
            if val is not None:
                service_charge = val

        if 'discount' in low or 'coupon' in low:
            val = _parse_money_from_line(line)
            if val is not None:
                discount = abs(val)

        if 'gst' in low or ('tax' in low and 'service' not in low):
            val = _parse_money_from_line(line)
            if val is not None:
                tax = val

        if 'round' in low:
            val = _parse_money_from_line(line)
            if val is not None:
                round_off = val

        if 'grand total' in low or ('total' in low and 'sub' not in low and 'service' not in low and 'tax' not in low and 'gst' not in low):
            val = _parse_money_from_line(line)
            if val is not None:
                grand_total = val

    return subtotal, service_charge, discount, tax, grand_total, round_off


def _parse_money_from_line(line: str) -> Optional[float]:
    """Extract money value from a line."""
    patterns = [
        r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*₹',
        r'(\d+(?:,\d+)*(?:\.\d+)?)',
    ]
    for pattern in patterns:
        m = re.search(pattern, line)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except ValueError:
                continue
    return None


@app.post("/api/split", response_model=SplitResponse)
async def split_bill(request: SplitRequest):
    """Split a bill given receipt image and description."""
    try:
        image_bytes = base64.b64decode(request.receipt_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    items, subtotal, service_charge, discount, tax, grand_total = parse_receipt_for_api(image_bytes)

    desc_info = parse_description_text(request.description)
    people = desc_info["people"]
    paid_by = desc_info["paid_by"]

    if not people:
        raise HTTPException(
            status_code=400,
            detail="Could not extract people names from description"
        )

    assumptions = []
    flags = []

    if paid_by is None:
        flags.append("No payer mentioned in description — cannot determine who paid")

    receipt_data = ReceiptData(
        items=items,
        subtotal=subtotal,
        service_charge=service_charge,
        discount=discount,
        tax=tax,
        grand_total=grand_total,
    )

    parsed = parser.parse(request.description, items)

    result = splitter.split(
        receipt=receipt_data,
        items=items,
        people=people,
        assignments=parsed["assignments"],
        personal=parsed["personal"],
        paid_by=paid_by,
        assumptions=parsed["assumptions"],
        flags=parsed["flags"],
        personal_each=parsed.get("personal_each", {}),
    )

    return result


@app.post("/api/split-manual", response_model=SplitResponse)
async def split_bill_manual(request: dict):
    """Split a bill with manually provided receipt data (for testing)."""
    receipt_data = ReceiptData(**request.get("receipt", {}))
    description = request.get("description", "")

    items = receipt_data.items
    people_info = parse_description_text(description)
    people = people_info["people"]
    paid_by = people_info["paid_by"]

    if not people:
        raise HTTPException(
            status_code=400,
            detail="Could not extract people names from description"
        )

    parsed = parser.parse(description, items)

    result = splitter.split(
        receipt=receipt_data,
        items=items,
        people=people,
        assignments=parsed["assignments"],
        personal=parsed["personal"],
        paid_by=paid_by,
        assumptions=parsed["assumptions"],
        flags=parsed["flags"],
        personal_each=parsed.get("personal_each", {}),
    )

    return result


@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
