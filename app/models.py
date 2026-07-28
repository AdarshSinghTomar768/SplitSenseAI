from pydantic import BaseModel
from typing import List, Optional


class ReceiptItem(BaseModel):
    name: str
    qty: int = 1
    amount: float


class ReceiptData(BaseModel):
    restaurant: str = ""
    date: str = ""
    bill_number: str = ""
    items: List[ReceiptItem]
    subtotal: float
    service_charge: float = 0
    discount: float = 0
    tax: float = 0
    round_off: float = 0
    grand_total: float
    service_charge_pct: float = 5.0
    tax_pct: float = 5.0


class SplitRequest(BaseModel):
    receipt_base64: str
    description: str


class PersonBreakdown(BaseModel):
    name: str
    items: List[str]
    subtotal: float
    tax_share: float
    service_share: float
    discount_share: float
    total: float


class Reconciliation(BaseModel):
    sum_of_person_totals: float
    matches_bill: bool


class SettleUp(BaseModel):
    from_name: str
    to_name: str
    amount: float


class SplitResponse(BaseModel):
    per_person: List[PersonBreakdown]
    grand_total: float
    reconciliation: Reconciliation
    paid_by: Optional[str]
    settle_up: List[SettleUp]
    assumptions: List[str]
    flags: List[str]
