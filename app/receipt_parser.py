import base64
import io
import re
import json
import os
from typing import Optional, Tuple, List

from PIL import Image

from .models import ReceiptData, ReceiptItem


def extract_receipt_from_image(image_bytes: bytes) -> ReceiptData:
    """Extract receipt data from image using OCR with structured parsing."""
    try:
        import pytesseract
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
        return parse_receipt_text(text)
    except Exception as e:
        raise ValueError(f"Failed to extract receipt: {e}")


def parse_receipt_text(text: str) -> ReceiptData:
    """Parse OCR text into structured receipt data."""
    lines = text.strip().split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    restaurant = ""
    date = ""
    bill_number = ""
    items: List[ReceiptItem] = []
    subtotal = 0.0
    service_charge = 0.0
    discount = 0.0
    tax = 0.0
    round_off = 0.0
    grand_total = 0.0
    service_pct = 5.0
    tax_pct = 5.0

    for i, line in enumerate(lines):
        low = line.lower()

        if i == 0 and not _parse_money(line):
            restaurant = line.strip()

        if re.search(r'bill\s*#?\s*(\w+)', low):
            m = re.search(r'bill\s*#?\s*(\w+)', low)
            if m:
                bill_number = m.group(1)

        date_match = re.search(r'(\d{1,2}[\s/\-]\w+[\s/\-]\d{2,4})', line)
        if date_match and not date:
            date = date_match.group(1)

        if 'subtotal' in low or 'sub total' in low or 'sub-total' in low:
            val = _parse_money(line)
            if val is not None:
                subtotal = val
            elif i + 1 < len(lines):
                val = _parse_money(lines[i + 1])
                if val is not None:
                    subtotal = val

        if 'service' in low and 'charge' not in low and '%' not in low and 'total' not in low:
            val = _parse_money(line)
            if val is not None:
                service_charge = val
            pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
            if pct_match:
                service_pct = float(pct_match.group(1))

        if 'service' in low and ('charge' in low or 'chrg' in low):
            val = _parse_money(line)
            if val is not None:
                service_charge = val

        if 'discount' in low or 'coupon' in low or 'off' in low:
            val = _parse_money(line)
            if val is not None:
                discount = abs(val)

        if 'gst' in low or 'tax' in low or 'cgst' in low or 'sgst' in low:
            val = _parse_money(line)
            if val is not None:
                tax = val

        if 'round' in low:
            val = _parse_money(line)
            if val is not None:
                round_off = val

        if 'grand total' in low or 'total' in low and 'sub' not in low and 'service' not in low and 'tax' not in low:
            val = _parse_money(line)
            if val is not None:
                grand_total = val

    if subtotal == 0 and items:
        subtotal = sum(item.amount * item.qty for item in items)

    if service_charge == 0 and subtotal > 0 and any('service' in l.lower() for l in lines):
        service_charge = round(subtotal * service_pct / 100)

    if grand_total == 0:
        grand_total = subtotal + service_charge - discount + tax + round_off

    return ReceiptData(
        restaurant=restaurant,
        date=date,
        bill_number=bill_number,
        items=items,
        subtotal=subtotal,
        service_charge=service_charge,
        discount=discount,
        tax=tax,
        round_off=round_off,
        grand_total=grand_total,
        service_charge_pct=service_pct,
        tax_pct=tax_pct,
    )


def extract_items_from_image(image_bytes: bytes) -> List[ReceiptItem]:
    """Extract individual line items from receipt image."""
    try:
        import pytesseract
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
        return parse_items_from_text(text)
    except Exception as e:
        raise ValueError(f"Failed to extract items: {e}")


def parse_items_from_text(text: str) -> List[ReceiptItem]:
    """Parse items from receipt OCR text."""
    lines = text.strip().split('\n')
    items: List[ReceiptItem] = []

    item_patterns = [
        r'^(.+?)\s+(\d+)\s+(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
        r'^(.+?)\s+(\d+)\s+₹?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
        r'^(.+?)\s+₹?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
        r'^(\D+?)\s+(\d+)\s+pc\s+(\d+(?:,\d+)*(?:\.\d+)?)\s*$',
    ]

    skip_keywords = [
        'subtotal', 'sub total', 'service', 'gst', 'tax', 'discount',
        'round', 'total', 'bill', 'grand', 'coupon', 'cgst', 'sgst',
        'amount', 'qty', 'item', 'price', 'date', 'time', 'table',
        'welcome', 'thank', 'copy', 'phone', ' gst ', 'inr', '₹',
        'ref', 'auth', 'card', 'cash', 'change', 'tip', 'SERVER',
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        low = line.lower()
        if any(kw in low for kw in skip_keywords):
            continue

        for pattern in item_patterns:
            m = re.match(pattern, line)
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    name = groups[0].strip()
                    qty = int(groups[1])
                    amount = _clean_amount(groups[2])
                elif len(groups) == 2:
                    name = groups[0].strip()
                    qty = 1
                    amount = _clean_amount(groups[1])
                else:
                    continue

                if name and amount > 0 and len(name) > 1:
                    items.append(ReceiptItem(name=name, qty=qty, amount=amount))
                break

    return items


def _parse_money(text: str) -> Optional[float]:
    """Extract a monetary value from text."""
    patterns = [
        r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*₹',
        r'(\d+(?:,\d+)*(?:\.\d+)?)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return _clean_amount(m.group(1))
    return None


def _clean_amount(s: str) -> float:
    """Clean and parse an amount string."""
    s = s.replace(',', '').replace('₹', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0
