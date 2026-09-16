from __future__ import annotations

from .models import RankedSupplier, SupplierResearch

WEIGHTS = {
    "price": 0.35,
    "credit": 0.25,
    "delivery": 0.20,
    "certifications": 0.15,
    "evidence": 0.05,
}

STATUS_MULTIPLIERS = {
    "confirmado": 1.0,
    "estimado": 0.8,
    "por_confirmar": 0.0,
}


def _apply_status_multiplier(score: float, status: str) -> float:
    return score * STATUS_MULTIPLIERS.get(status, 0.0)


def _price_scores(
    suppliers: list[SupplierResearch],
) -> dict[str, float]:
    eligible = [
        supplier
        for supplier in suppliers
        if supplier.product_match_status == "confirmado"
        and supplier.price_status != "por_confirmar"
    ]

    delivered_totals = [
        supplier.estimated_total_delivered_cop
        for supplier in eligible
        if supplier.estimated_total_delivered_cop is not None
        and supplier.estimated_total_delivered_cop > 0
    ]

    unit_prices = [
        supplier.price_cop_per_unit
        for supplier in eligible
        if supplier.price_cop_per_unit is not None
        and supplier.price_cop_per_unit > 0
    ]

    if len(delivered_totals) >= 2:
        def price_value(
            supplier: SupplierResearch,
        ) -> float | None:
            return supplier.estimated_total_delivered_cop

        available = delivered_totals
    elif unit_prices:
        def price_value(
            supplier: SupplierResearch,
        ) -> float | None:
            return supplier.price_cop_per_unit

        available = unit_prices
    elif delivered_totals:
        def price_value(
            supplier: SupplierResearch,
        ) -> float | None:
            return supplier.estimated_total_delivered_cop

        available = delivered_totals
    else:
        return {
            supplier.supplier_name: 0.0
            for supplier in suppliers
        }

    minimum = min(available)
    scores: dict[str, float] = {}

    for supplier in suppliers:
        if (
            supplier.product_match_status != "confirmado"
            or supplier.price_status == "por_confirmar"
        ):
            scores[supplier.supplier_name] = 0.0
            continue

        value = price_value(supplier)

        if value is None or value <= 0:
            scores[supplier.supplier_name] = 0.0
            continue

        base_score = max(
            20.0,
            min(100.0, 100.0 * minimum / value),
        )

        scores[supplier.supplier_name] = (
            _apply_status_multiplier(
                base_score,
                supplier.price_status,
            )
        )

    return scores


def _credit_score(s: SupplierResearch) -> float:
    if s.credit_days is None:
        return 0.0

    days = max(0, s.credit_days)

    if days >= 60:
        base_score = 100.0
    elif days >= 45:
        base_score = 90.0
    elif days >= 30:
        base_score = 80.0
    elif days >= 15:
        base_score = 60.0
    else:
        base_score = 30.0

    return _apply_status_multiplier(base_score, s.credit_status)


def _delivery_score(s: SupplierResearch) -> float:
    if s.delivery_days is None:
        return 0.0

    days = s.delivery_days

    if days <= 1:
        base_score = 100.0
    elif days <= 2:
        base_score = 90.0
    elif days <= 3:
        base_score = 80.0
    elif days <= 5:
        base_score = 65.0
    elif days <= 7:
        base_score = 50.0
    elif days <= 14:
        base_score = 30.0
    else:
        base_score = 15.0

    return _apply_status_multiplier(base_score, s.delivery_status)


def _looks_like_certification(value: str) -> bool:
    normalized = value.strip().lower()

    if not normalized or normalized == "por confirmar":
        return False

    generic_labels = {
        "epp",
        "elementos de protección personal",
        "elementos de protección personal (epp)",
        "equipo de protección personal",
        "equipos de protección personal",
    }

    if normalized in generic_labels:
        return False

    certification_markers = (
        "iso ",
        "iso-",
        "invima",
        "registro sanitario",
        "haccp",
        "astm ",
        "ansi ",
        "ntc ",
        "certificado",
        "certificación",
    )

    return any(
        marker in normalized
        for marker in certification_markers
    )


def _certifications_score(s: SupplierResearch) -> float:
    certifications = [
        certification
        for certification in s.certifications
        if _looks_like_certification(certification)
    ]
    count = len(certifications)

    if count == 0:
        return 0.0

    if count >= 2:
        base_score = 100.0
    else:
        base_score = 80.0

    return _apply_status_multiplier(
        base_score,
        s.certifications_status,
    )


def _evidence_score(s: SupplierResearch) -> float:
    if not s.sources:
        return 0.0

    return {
        "alta": 100.0,
        "media": 70.0,
        "baja": 40.0,
    }.get(s.confidence, 50.0)


def rank_suppliers(suppliers: list[SupplierResearch]) -> list[RankedSupplier]:
    p_scores = _price_scores(suppliers)
    rows = []

    for s in suppliers:
        ps = p_scores.get(s.supplier_name, 0.0)
        cs = _credit_score(s)
        ds = _delivery_score(s)
        certs = _certifications_score(s)
        es = _evidence_score(s)

        score = (
            ps * WEIGHTS["price"]
            + cs * WEIGHTS["credit"]
            + ds * WEIGHTS["delivery"]
            + certs * WEIGHTS["certifications"]
            + es * WEIGHTS["evidence"]
        )

        rows.append(
            RankedSupplier(
                rank=0,
                score=round(score, 1),
                price_score=round(ps, 1),
                credit_score=round(cs, 1),
                delivery_score=round(ds, 1),
                certifications_score=round(certs, 1),
                evidence_score=round(es, 1),
                supplier=s,
            )
        )

    rows.sort(key=lambda row: row.score, reverse=True)

    for index, row in enumerate(rows, start=1):
        row.rank = index

    return rows
