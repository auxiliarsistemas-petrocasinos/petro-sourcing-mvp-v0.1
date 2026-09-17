from __future__ import annotations

import unicodedata

from .models import SupplierResearch

INELIGIBLE_SUPPLIER_TYPE_MARKERS = (
    "marketplace",
    "directorio",
    "multiples vendedores",
    "multi-vendor",
    "multivendedor",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value.strip().lower(),
    )
    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


def is_supplier_eligible(
    supplier: SupplierResearch,
) -> bool:
    if supplier.availability_status == "sin_stock":
        return False

    if supplier.fulfillment_status == "insuficiente":
        return False

    supplier_type = _normalize_text(
        supplier.supplier_type or ""
    )

    return not any(
        marker in supplier_type
        for marker in INELIGIBLE_SUPPLIER_TYPE_MARKERS
    )
