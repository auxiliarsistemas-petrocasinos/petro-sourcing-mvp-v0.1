from __future__ import annotations

from statistics import median

from .models import SupplierResearch

EXTREMELY_LOW_PRICE_RATIO = 0.50
EXTREMELY_LOW_PRICE_REASON = (
    "extremely_low_vs_comparable_median"
)


def reset_price_review_statuses(
    suppliers: list[SupplierResearch],
) -> None:
    for supplier in suppliers:
        # Una validación manual futura debe sobrevivir
        # a nuevos cálculos de ranking.
        if supplier.price_review_status == "validated":
            continue

        supplier.price_review_status = "not_required"
        supplier.price_review_reason = None


def flag_anomalously_low_prices(
    entries: list[tuple[SupplierResearch, float]],
) -> None:
    # Con una o dos observaciones no inferimos anomalías.
    if len(entries) < 3:
        return

    reference = median(
        value
        for _, value in entries
    )

    if reference <= 0:
        return

    threshold = reference * EXTREMELY_LOW_PRICE_RATIO

    for supplier, value in entries:
        if supplier.price_review_status == "validated":
            continue

        if value < threshold:
            supplier.price_review_status = "requires_review"
            supplier.price_review_reason = (
                EXTREMELY_LOW_PRICE_REASON
            )
