#!/usr/bin/env python3
"""Test suite for Fair Split API — validates against all 4 sample receipts."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import ReceiptData, ReceiptItem
from app.description_parser import DescriptionParser
from app.splitter import BillSplitter

parser = DescriptionParser()
splitter = BillSplitter()

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
results = []


def test(name, actual, expected, tolerance=1):
    if isinstance(actual, float) and isinstance(expected, float):
        ok = abs(actual - expected) <= tolerance
    else:
        ok = actual == expected
    status = PASS if ok else FAIL
    results.append((name, ok))
    if not ok:
        print(f"  {status} {name}: expected {expected}, got {actual}")
    else:
        print(f"  {status} {name}")
    return ok


def compute_expected_settle_up(breakdowns, paid_by):
    settle = []
    for bd in breakdowns:
        if bd.name != paid_by and bd.total > 0:
            settle.append({"from": bd.name, "to": paid_by, "amount": bd.total})
    return settle


def run_test_r1():
    print("\n=== R1: Brew & Bite Café ===")
    items = [
        ReceiptItem(name="Cappuccino", qty=1, amount=180),
        ReceiptItem(name="Grilled Chicken Sandwich", qty=1, amount=260),
        ReceiptItem(name="Penne Arrabiata", qty=1, amount=320),
        ReceiptItem(name="Fresh Lime Soda", qty=1, amount=120),
        ReceiptItem(name="Brownie", qty=1, amount=160),
    ]
    receipt = ReceiptData(
        items=items, subtotal=1040, service_charge=52, tax=54.60,
        grand_total=1147, service_charge_pct=5.0, tax_pct=5.0,
    )
    desc = "Three of us — Ravi, Neha, Sameer. Ravi had the cappuccino and the sandwich. Neha had the pasta and the lime soda. Sameer had the brownie. Sameer paid."

    parsed = parser.parse(desc, items)
    people = parsed["people"]
    paid_by = parsed["paid_by"]

    print(f"  People: {people}")
    print(f"  Paid by: {paid_by}")
    print(f"  Assignments: {parsed['assignments']}")
    print(f"  Personal: {parsed['personal']}")

    result = splitter.split(receipt, items, people, parsed["assignments"], parsed["personal"], paid_by, parsed["assumptions"], parsed["flags"], personal_each=parsed.get("personal_each", {}))

    print(f"\n  Results:")
    for p in result.per_person:
        print(f"    {p.name}: items={p.items}, sub={p.subtotal}, tax={p.tax_share}, svc={p.service_share}, disc={p.discount_share}, total={p.total}")
    print(f"    Grand total: {result.grand_total}")
    print(f"    Reconciliation: sum={result.reconciliation.sum_of_person_totals}, matches={result.reconciliation.matches_bill}")
    print(f"    Settle up: {[(s.from_name, s.to_name, s.amount) for s in result.settle_up]}")

    # Expected:
    # Ravi: Cappuccino(180) + Sandwich(260) = 440
    # Neha: Pasta(320) + Lime Soda(120) = 440
    # Sameer: Brownie(160) = 160
    # Total pre-tax = 1040
    # Tax: Ravi=440/1040*54.60≈23, Neha=440/1040*54.60≈23, Sameer=160/1040*54.60≈8
    # Service: Ravi=440/1040*52≈22, Neha=440/1040*52≈22, Sameer=160/1040*52≈8
    # Ravi total = 440+23+22 = 485
    # Neha total = 440+23+22 = 485
    # Sameer total = 160+8+8 = 176
    # Sum = 1146 ≈ 1147 (rounding)

    ravi = next(p for p in result.per_person if p.name == "Ravi")
    neha = next(p for p in result.per_person if p.name == "Neha")
    sameer = next(p for p in result.per_person if p.name == "Sameer")

    test("Ravi subtotal", ravi.subtotal, 440)
    test("Neha subtotal", neha.subtotal, 440)
    test("Sameer subtotal", sameer.subtotal, 160)
    test("Ravi total", ravi.total, 485, tolerance=5)
    test("Neha total", neha.total, 485, tolerance=5)
    test("Sameer total", sameer.total, 176, tolerance=5)
    test("Grand total", result.grand_total, 1147)
    test("Paid by", paid_by, "Sameer")

    return result


def run_test_r2():
    print("\n=== R2: Tamarind Kitchen ===")
    items = [
        ReceiptItem(name="Paneer Butter Masala", qty=1, amount=320),
        ReceiptItem(name="Dal Makhani", qty=1, amount=260),
        ReceiptItem(name="Butter Naan", qty=4, amount=240),
        ReceiptItem(name="Jeera Rice", qty=1, amount=180),
        ReceiptItem(name="Gulab Jamun", qty=2, amount=120),
        ReceiptItem(name="Masala Papad", qty=2, amount=100),
    ]
    receipt = ReceiptData(
        items=items, subtotal=1220, service_charge=61, tax=64.05,
        grand_total=1345, service_charge_pct=5.0, tax_pct=5.0,
    )
    desc = "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."

    parsed = parser.parse(desc, items)
    people = parsed["people"]
    paid_by = parsed["paid_by"]

    print(f"  People: {people}")
    print(f"  Paid by: {paid_by}")
    print(f"  Assignments: {parsed['assignments']}")
    print(f"  Personal: {parsed['personal']}")

    result = splitter.split(receipt, items, people, parsed["assignments"], parsed["personal"], paid_by, parsed["assumptions"], parsed["flags"], personal_each=parsed.get("personal_each", {}))

    print(f"\n  Results:")
    for p in result.per_person:
        print(f"    {p.name}: items={p.items}, sub={p.subtotal}, tax={p.tax_share}, svc={p.service_share}, disc={p.discount_share}, total={p.total}")
    print(f"    Grand total: {result.grand_total}")
    print(f"    Reconciliation: sum={result.reconciliation.sum_of_person_totals}, matches={result.reconciliation.matches_bill}")
    print(f"    Settle up: {[(s.from_name, s.to_name, s.amount) for s in result.settle_up]}")

    # Expected:
    # Non-shared: 320+260+240+180+100 = 1100, split 4 ways = 275 each
    # Shared (Gulab Jamun): 120, split between Priya and Karan = 60 each
    # Aman subtotal = 275
    # Priya subtotal = 275 + 60 = 335
    # Karan subtotal = 275 + 60 = 335
    # Sara subtotal = 275
    # Total pre-tax = 1220
    # Tax per person proportional
    # Service per person proportional

    aman = next(p for p in result.per_person if p.name == "Aman")
    priya = next(p for p in result.per_person if p.name == "Priya")
    karan = next(p for p in result.per_person if p.name == "Karan")
    sara = next(p for p in result.per_person if p.name == "Sara")

    test("Aman subtotal", aman.subtotal, 275)
    test("Priya subtotal", priya.subtotal, 335)
    test("Karan subtotal", karan.subtotal, 335)
    test("Sara subtotal", sara.subtotal, 275)
    test("Grand total", result.grand_total, 1345)
    test("Paid by", paid_by, "Priya")

    # Verify reconciliation
    test("Reconciliation matches", result.reconciliation.matches_bill, True)

    return result


def run_test_r3():
    print("\n=== R3: The Daily Grind ===")
    items = [
        ReceiptItem(name="Margherita Pizza", qty=1, amount=380),
        ReceiptItem(name="Arrabiata Pasta", qty=1, amount=340),
        ReceiptItem(name="Garlic Bread", qty=1, amount=160),
        ReceiptItem(name="Craft Beer", qty=2, amount=500),
        ReceiptItem(name="Virgin Mojito", qty=1, amount=180),
    ]
    receipt = ReceiptData(
        items=items, subtotal=1560, service_charge=78, tax=81.90,
        grand_total=1720, service_charge_pct=5.0, tax_pct=5.0,
    )
    desc = "Ishaan, Meera, Rohit. Pizza, pasta and garlic bread shared equally by all three. The two beers were Ishaan and Rohit only. The mojito was Meera's. Rohit paid."

    parsed = parser.parse(desc, items)
    people = parsed["people"]
    paid_by = parsed["paid_by"]

    print(f"  People: {people}")
    print(f"  Paid by: {paid_by}")
    print(f"  Assignments: {parsed['assignments']}")
    print(f"  Personal: {parsed['personal']}")

    result = splitter.split(receipt, items, people, parsed["assignments"], parsed["personal"], paid_by, parsed["assumptions"], parsed["flags"], personal_each=parsed.get("personal_each", {}))

    print(f"\n  Results:")
    for p in result.per_person:
        print(f"    {p.name}: items={p.items}, sub={p.subtotal}, tax={p.tax_share}, svc={p.service_share}, disc={p.discount_share}, total={p.total}")
    print(f"    Grand total: {result.grand_total}")
    print(f"    Reconciliation: sum={result.reconciliation.sum_of_person_totals}, matches={result.reconciliation.matches_bill}")
    print(f"    Settle up: {[(s.from_name, s.to_name, s.amount) for s in result.settle_up]}")

    # Expected:
    # Shared (380+340+160=880): split 3 ways ≈ 293.33 each
    # Beer (500): Ishaan and Rohit only = 250 each
    # Mojito (180): Meera only
    # Ishaan subtotal = 293.33 + 250 = 543.33
    # Meera subtotal = 293.33 + 180 = 473.33
    # Rohit subtotal = 293.33 + 250 = 543.33
    # Total = 1560

    ishaan = next(p for p in result.per_person if p.name == "Ishaan")
    meera = next(p for p in result.per_person if p.name == "Meera")
    rohit = next(p for p in result.per_person if p.name == "Rohit")

    test("Ishaan subtotal", ishaan.subtotal, 543, tolerance=2)
    test("Meera subtotal", meera.subtotal, 473, tolerance=2)
    test("Rohit subtotal", rohit.subtotal, 543, tolerance=2)
    test("Grand total", result.grand_total, 1720)
    test("Paid by", paid_by, "Rohit")
    test("Reconciliation matches", result.reconciliation.matches_bill, True)

    return result


def run_test_r4():
    print("\n=== R4: Spice Route ===")
    items = [
        ReceiptItem(name="Chicken Biryani", qty=2, amount=560),
        ReceiptItem(name="Veg Biryani", qty=1, amount=240),
        ReceiptItem(name="Mutton Rogan Josh", qty=1, amount=420),
        ReceiptItem(name="Raita", qty=2, amount=120),
        ReceiptItem(name="Soft Drinks", qty=3, amount=180),
    ]
    receipt = ReceiptData(
        items=items, subtotal=1520, discount=228, service_charge=76, tax=68.40,
        grand_total=1436, service_charge_pct=5.0, tax_pct=5.0,
    )
    desc = "Dev and Nikhil each had a chicken biryani. Anjali had the veg biryani. Farah had the rogan josh. The raita and soft drinks were common to all four. We used a 15% off coupon. Anjali paid."

    parsed = parser.parse(desc, items)
    people = parsed["people"]
    paid_by = parsed["paid_by"]

    print(f"  People: {people}")
    print(f"  Paid by: {paid_by}")
    print(f"  Assignments: {parsed['assignments']}")
    print(f"  Personal: {parsed['personal']}")

    result = splitter.split(receipt, items, people, parsed["assignments"], parsed["personal"], paid_by, parsed["assumptions"], parsed["flags"], personal_each=parsed.get("personal_each", {}))

    print(f"\n  Results:")
    for p in result.per_person:
        print(f"    {p.name}: items={p.items}, sub={p.subtotal}, tax={p.tax_share}, svc={p.service_share}, disc={p.discount_share}, total={p.total}")
    print(f"    Grand total: {result.grand_total}")
    print(f"    Reconciliation: sum={result.reconciliation.sum_of_person_totals}, matches={result.reconciliation.matches_bill}")
    print(f"    Settle up: {[(s.from_name, s.to_name, s.amount) for s in result.settle_up]}")

    # Expected:
    # Dev: Chicken Biryani(560/2=280 per portion but qty=2, total=560, he had one) 
    # Wait, "Dev and Nikhil each had a chicken biryani" — qty=2, amount=560
    # That means total for 2 biryanis = 560, so each person pays 280
    # Actually the bill says qty=2, amount=560 for Chicken Biryani. 
    # "Each had a chicken biryani" means Dev had one, Nikhil had one.
    # So Dev's share of biryani = 560/2 = 280
    # Nikhil's share = 560/2 = 280
    # Anjali: Veg Biryani = 240
    # Farah: Mutton Rogan Josh = 420
    # Raita + Soft Drinks (120+180=300) shared by all 4 = 75 each
    # Dev subtotal = 280 + 75 = 355
    # Nikhil subtotal = 280 + 75 = 355
    # Anjali subtotal = 240 + 75 = 315
    # Farah subtotal = 420 + 75 = 495
    # Total = 355+355+315+495 = 1520

    # Discount: 228, proportional
    # Dev disc = 355/1520*228 ≈ 53
    # Nikhil disc = 355/1520*228 ≈ 53
    # Anjali disc = 315/1520*228 ≈ 47
    # Farah disc = 495/1520*228 ≈ 74
    # Service: 76, proportional
    # Dev svc = 355/1520*76 ≈ 18
    # Nikhil svc = 355/1520*76 ≈ 18
    # Anjali svc = 315/1520*76 ≈ 16
    # Farah svc = 495/1520*76 ≈ 25
    # Tax: 68.40, proportional
    # Dev tax = 355/1520*68.40 ≈ 16
    # Nikhil tax = 355/1520*68.40 ≈ 16
    # Anjali tax = 315/1520*68.40 ≈ 14
    # Farah tax = 495/1520*68.40 ≈ 22

    dev = next(p for p in result.per_person if p.name == "Dev")
    nikhil = next(p for p in result.per_person if p.name == "Nikhil")
    anjali = next(p for p in result.per_person if p.name == "Anjali")
    farah = next(p for p in result.per_person if p.name == "Farah")

    test("Dev subtotal", dev.subtotal, 355)
    test("Nikhil subtotal", nikhil.subtotal, 355)
    test("Anjali subtotal", anjali.subtotal, 315)
    test("Farah subtotal", farah.subtotal, 495)
    test("Grand total", result.grand_total, 1436)
    test("Paid by", paid_by, "Anjali")
    test("Reconciliation matches", result.reconciliation.matches_bill, True)
    test("Has discount", result.per_person[0].discount_share != 0, True)

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  FAIR SPLIT — TEST SUITE")
    print("=" * 60)

    run_test_r1()
    run_test_r2()
    run_test_r3()
    run_test_r4()

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    sys.exit(0 if passed == total else 1)
