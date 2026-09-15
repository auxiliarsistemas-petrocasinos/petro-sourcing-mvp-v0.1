from __future__ import annotations

from .models import RankedSupplier, SupplierResearch

WEIGHTS = {
    "price": 0.35,
    "credit": 0.25,
    "delivery": 0.20,
    "certifications": 0.15,
    "evidence": 0.05,
}


def _price_scores(suppliers: list[SupplierResearch]) -> dict[str, float]:
    available = [
        s.estimated_total_delivered_cop
        for s in suppliers
        if s.estimated_total_delivered_cop is not None and s.estimated_total_delivered_cop > 0
    ]
    if not available:
        return {s.supplier_name: 0.0 for s in suppliers}

    minimum = min(available)
    scores = {}
    for s in suppliers:
        value = s.estimated_total_delivered_cop
        if value is None or value <= 0:
            scores[s.supplier_name] = 0.0
        else:
            # El proveedor más barato obtiene 100. Los demás bajan de forma proporcional.
            scores[s.supplier_name] = max(20.0, min(100.0, 100.0 * minimum / value))
    return scores


def _credit_score(s: SupplierResearch) -> float:
    if s.credit_days is None:
        return 0.0 if s.credit_status == "por_confirmar" else 45.0
    days = max(0, s.credit_days)
    if days >= 60:
        return 100.0
    if days >= 45:
        return 90.0
    if days >= 30:
        return 80.0
    if days >= 15:
        return 60.0
    return 30.0


def _delivery_score(s: SupplierResearch) -> float:
    if s.delivery_days is None:
        return 0.0 if s.delivery_status == "por_confirmar" else 45.0
    d = s.delivery_days
    if d <= 1:
        return 100.0
    if d <= 2:
        return 90.0
    if d <= 3:
        return 80.0
    if d <= 5:
        return 65.0
    if d <= 7:
        return 50.0
    if d <= 14:
        return 30.0
    return 15.0


def _certifications_score(s: SupplierResearch) -> float:
    count = len([c for c in s.certifications if c and c.lower() != "por confirmar"])
    if s.certifications_status == "por_confirmar" and count == 0:
        return 0.0
    if count >= 2:
        return 100.0
    if count == 1:
        return 80.0
    return 20.0


def _evidence_score(s: SupplierResearch) -> float:
    if not s.sources:
        return 0.0

    return {"alta": 100.0, "media": 70.0, "baja": 40.0}.get(s.confidence, 50.0)


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

    rows.sort(key=lambda r: r.score, reverse=True)
    for i, row in enumerate(rows, start=1):
        row.rank = i
    return rows
