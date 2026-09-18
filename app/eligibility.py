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


def supplier_ineligibility_reason(
    supplier: SupplierResearch,
) -> str | None:
    if supplier.availability_status == "sin_stock":
        return "sin_stock"

    if supplier.fulfillment_status == "insuficiente":
        return "capacidad_insuficiente"

    supplier_type = _normalize_text(
        supplier.supplier_type or ""
    )

    if any(
        marker in supplier_type
        for marker in INELIGIBLE_SUPPLIER_TYPE_MARKERS
    ):
        return "tipo_no_elegible"

    return None


def is_supplier_eligible(
    supplier: SupplierResearch,
) -> bool:
    return supplier_ineligibility_reason(supplier) is None
