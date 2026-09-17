from __future__ import annotations

import unicodedata

from .eligibility import is_supplier_eligible
from .models import RankedSupplier, SupplierResearch
from .price_review import (
    flag_anomalously_low_prices,
    reset_price_review_statuses,
)

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


UNKNOWN_PRICE_LABELS = {
    "",
    "por confirmar",
    "n/a",
    "none",
}


def _normalize_price_label(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        (value or "").strip().lower(),
    )
    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


def _structured_price_value(
    supplier: SupplierResearch,
) -> tuple[str, float] | None:
    amount = supplier.price_amount_cop

    if amount is None or amount <= 0:
        return None

    basis = _normalize_price_label(
        supplier.price_basis
    )
    base_unit = _normalize_price_label(
        supplier.price_base_unit
    )

    if base_unit in UNKNOWN_PRICE_LABELS:
        return None

    quantity = supplier.price_basis_quantity

    if quantity is not None:
        if quantity <= 0:
            return None

        return (
            base_unit,
            amount / quantity,
        )

    if basis == base_unit:
        return (
            base_unit,
            amount,
        )

    return None


def _apply_price_group(
    entries: list[tuple[SupplierResearch, float]],
    scores: dict[str, float],
) -> None:
    entries = [
        (supplier, value)
        for supplier, value in entries
        if supplier.price_review_status != "requires_review"
    ]

    if len(entries) < 2:
        return

    minimum = min(
        value
        for _, value in entries
    )

    for supplier, value in entries:
        base_score = max(
            20.0,
            min(
                100.0,
                100.0 * minimum / value,
            ),
        )

        scores[supplier.supplier_name] = (
            _apply_status_multiplier(
                base_score,
                supplier.price_status,
            )
        )


def _price_scores(
    suppliers: list[SupplierResearch],
) -> dict[str, float]:
    scores = {
        supplier.supplier_name: 0.0
        for supplier in suppliers
    }

    reset_price_review_statuses(suppliers)

    eligible = [
        supplier
        for supplier in suppliers
        if is_supplier_eligible(supplier)
        and supplier.product_match_status == "confirmado"
        and supplier.price_status != "por_confirmar"
    ]

    delivered = [
        (
            supplier,
            supplier.estimated_total_delivered_cop,
        )
        for supplier in eligible
        if supplier.estimated_total_delivered_cop is not None
        and supplier.estimated_total_delivered_cop > 0
    ]

    # El costo total puesto en destino es la comparación
    # preferida cuando existen al menos dos alternativas.
    if len(delivered) >= 2:
        flag_anomalously_low_prices(delivered)

        _apply_price_group(
            [
                (supplier, value)
                for supplier, value in delivered
                if value is not None
            ],
            scores,
        )
        return scores

    comparable_groups: dict[
        str,
        list[tuple[SupplierResearch, float]],
    ] = {}

    for supplier in eligible:
        normalized = _structured_price_value(
            supplier
        )

        if normalized is None:
            continue

        base_unit, value = normalized

        comparable_groups.setdefault(
            base_unit,
            [],
        ).append(
            (supplier, value)
        )

    for entries in comparable_groups.values():
        flag_anomalously_low_prices(entries)

        _apply_price_group(
            entries,
            scores,
        )

    return scores


THIRD_PARTY_CREDIT_MARKERS = (
    "mercadopago",
    "mercado pago",
    "tarjeta de credito",
    "pasarela de pago",
    "pasarela de pagos",
    "shopify payments",
    "addi",
    "sistecredito",
    "payu",
    "wompi",
    "difierelo",
    "cuotas sin interes",
)


def _normalize_credit_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value.strip().lower(),
    )
    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


def _is_third_party_credit(
    supplier: SupplierResearch,
) -> bool:
    terms = _normalize_credit_text(
        supplier.credit_terms or ""
    )

    return any(
        marker in terms
        for marker in THIRD_PARTY_CREDIT_MARKERS
    )


def _credit_score(s: SupplierResearch) -> float:
    if s.credit_days is None or s.credit_days <= 0:
        return 0.0

    if _is_third_party_credit(s):
        return 0.0

    days = s.credit_days

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
        if (
            not is_supplier_eligible(s)
            or s.product_match_status != "confirmado"
        ):
            ps = 0.0
            cs = 0.0
            ds = 0.0
            certs = 0.0
            es = 0.0
        else:
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

    rows.sort(
        key=lambda row: (
            row.score,
            is_supplier_eligible(row.supplier),
            row.supplier.product_match_status == "confirmado",
        ),
        reverse=True,
    )

    for index, row in enumerate(rows, start=1):
        row.rank = index

    return rows
