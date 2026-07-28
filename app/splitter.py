from typing import List, Dict, Optional
from .models import (
    ReceiptData, ReceiptItem, PersonBreakdown, Reconciliation,
    SettleUp, SplitResponse
)


class BillSplitter:
    """Split a bill according to fairness rules."""

    def split(
        self,
        receipt: ReceiptData,
        items: List[ReceiptItem],
        people: List[str],
        assignments: Dict[int, List[str]],
        personal: Dict[int, str],
        paid_by: Optional[str],
        assumptions: List[str],
        flags: List[str],
        personal_each: Optional[Dict[int, List[str]]] = None,
    ) -> SplitResponse:
        """
        Fairness rules:
        1. Each person pays for items they consumed
        2. Shared items split equally among sharers
        3. Tax + service allocated proportional to pre-tax subtotal
        4. Discount allocated proportional to subtotal
        5. Round to rupee; state in assumptions who absorbs leftover paise
        """
        if personal_each is None:
            personal_each = {}

        effective_items = items if items else receipt.items
        if not effective_items:
            effective_items = receipt.items

        person_subtotals: Dict[str, float] = {p: 0.0 for p in people}
        person_items: Dict[str, List[str]] = {p: [] for p in people}

        for idx, item in enumerate(effective_items):
            item_total = item.amount * item.qty

            if idx in personal:
                # Single person owns this entire item
                owner = personal[idx]
                if owner == "I" and paid_by and paid_by != "I":
                    owner = paid_by
                elif owner == "I":
                    owner = people[0] if people else "Unknown"

                if owner not in person_subtotals:
                    person_subtotals[owner] = 0.0
                    person_items[owner] = []
                person_subtotals[owner] += item_total
                display_name = f"{item.name}" if item.qty == 1 else f"{item.name} (×{item.qty})"
                person_items[owner].append(display_name)

            elif idx in personal_each:
                # "X and Y each had a Z" — each person pays for their own portion
                who = personal_each[idx]
                portion_each = item_total / len(who)
                display_name = item.name
                for person in who:
                    if person not in person_subtotals:
                        person_subtotals[person] = 0.0
                        person_items[person] = []
                    person_subtotals[person] += portion_each
                    person_items[person].append(f"{display_name} (each)")

            elif idx in assignments:
                sharers = assignments[idx]
                if not sharers:
                    sharers = list(people)

                share_each = item_total / len(sharers)
                display_name = f"{item.name}" if item.qty == 1 else f"{item.name} (×{item.qty})"

                for person in sharers:
                    if person not in person_subtotals:
                        person_subtotals[person] = 0.0
                        person_items[person] = []
                    person_subtotals[person] += share_each
                    person_items[person].append(f"{display_name} (÷{len(sharers)})")
            else:
                share_each = item_total / len(people) if people else item_total
                display_name = f"{item.name}" if item.qty == 1 else f"{item.name} (×{item.qty})"
                for person in people:
                    person_subtotals[person] += share_each
                    person_items[person].append(f"{display_name} (÷{len(people)})")

        total_pre_tax = sum(person_subtotals.values())
        if total_pre_tax == 0:
            total_pre_tax = 1

        service_total = receipt.service_charge
        tax_total = receipt.tax
        discount_total = receipt.discount

        person_breakdowns: List[PersonBreakdown] = []
        sum_of_totals = 0.0

        for person in people:
            proportion = person_subtotals[person] / total_pre_tax if total_pre_tax > 0 else 1 / len(people)

            tax_share = round(tax_total * proportion, 2)
            service_share = round(service_total * proportion, 2)
            discount_share = round(discount_total * proportion, 2)

            total = round(person_subtotals[person] + tax_share + service_share - discount_share, 2)

            person_breakdowns.append(PersonBreakdown(
                name=person,
                items=person_items[person],
                subtotal=round(person_subtotals[person], 2),
                tax_share=tax_share,
                service_share=service_share,
                discount_share=-discount_share if discount_share > 0 else discount_share,
                total=total,
            ))
            sum_of_totals += total

        grand_total = round(receipt.grand_total, 2)
        matches_bill = abs(sum_of_totals - grand_total) <= 0.05

        if not matches_bill:
            diff = grand_total - sum_of_totals
            flags.append(
                f"Split total (€{round(sum_of_totals, 2)}) doesn't match bill total (€{grand_total}) — €{abs(round(diff, 2))} difference"
            )

        settle_up = self._compute_settle_up(person_breakdowns, paid_by, people)

        return SplitResponse(
            per_person=person_breakdowns,
            grand_total=grand_total,
            reconciliation=Reconciliation(
                sum_of_person_totals=round(sum_of_totals, 2),
                matches_bill=matches_bill,
            ),
            paid_by=paid_by,
            settle_up=settle_up,
            assumptions=assumptions,
            flags=flags,
        )

    def _compute_settle_up(
        self,
        breakdowns: List[PersonBreakdown],
        paid_by: Optional[str],
        people: List[str],
    ) -> List[SettleUp]:
        """Compute who owes whom."""
        if not paid_by or paid_by == "I":
            return []

        settle_up: List[SettleUp] = []
        for bd in breakdowns:
            if bd.name != paid_by and bd.total > 0:
                settle_up.append(SettleUp(
                    from_name=bd.name,
                    to_name=paid_by,
                    amount=bd.total,
                ))

        return settle_up
