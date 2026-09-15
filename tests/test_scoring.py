from app.models import Source, SupplierResearch
from app.scoring import rank_suppliers


def supplier(
    name: str,
    *,
    total: float | None = None,
    price_status: str = "por_confirmar",
    credit_days: int | None = None,
    credit_status: str = "por_confirmar",
    delivery_days: float | None = None,
    delivery_status: str = "por_confirmar",
    certifications: list[str] | None = None,
    certifications_status: str = "por_confirmar",
    confidence: str = "media",
    sources: list[Source] | None = None,
) -> SupplierResearch:
    return SupplierResearch(
        supplier_name=name,
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=total,
        price_status=price_status,
        credit_days=credit_days,
        credit_status=credit_status,
        delivery_days=delivery_days,
        delivery_status=delivery_status,
        certifications=certifications or [],
        certifications_status=certifications_status,
        evidence_summary="Proveedor usado para pruebas.",
        confidence=confidence,
        sources=sources or [],
    )


def row_for(supplier_item: SupplierResearch):
    return rank_suppliers([supplier_item])[0]


def test_cheapest_known_price_gets_highest_price_score():
    cheap = supplier("Proveedor barato", total=100_000, price_status="confirmado")
    expensive = supplier("Proveedor caro", total=125_000, price_status="confirmado")

    ranking = rank_suppliers([expensive, cheap])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Proveedor barato"].price_score == 100.0
    assert rows["Proveedor caro"].price_score == 80.0


def test_missing_price_does_not_receive_artificial_price_points():
    known = supplier("Precio conocido", total=100_000, price_status="confirmado")
    unknown = supplier("Precio desconocido")

    ranking = rank_suppliers([unknown, known])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Precio conocido"].price_score == 100.0
    assert rows["Precio desconocido"].price_score == 0.0
    assert rows["Precio conocido"].rank < rows["Precio desconocido"].rank


def test_all_missing_prices_receive_zero_price_score():
    first = supplier("Proveedor A")
    second = supplier("Proveedor B")

    ranking = rank_suppliers([first, second])

    assert all(row.price_score == 0.0 for row in ranking)


def test_unknown_credit_receives_zero_credit_score():
    row = row_for(supplier("Crédito desconocido"))

    assert row.credit_score == 0.0


def test_confirmed_credit_is_scored_by_days():
    row = row_for(
        supplier(
            "Crédito 30 días",
            credit_days=30,
            credit_status="confirmado",
        )
    )

    assert row.credit_score == 80.0


def test_unknown_delivery_receives_zero_delivery_score():
    row = row_for(supplier("Entrega desconocida"))

    assert row.delivery_score == 0.0


def test_confirmed_delivery_is_scored_by_days():
    row = row_for(
        supplier(
            "Entrega rápida",
            delivery_days=2,
            delivery_status="confirmado",
        )
    )

    assert row.delivery_score == 90.0


def test_unknown_certifications_receive_zero_certification_score():
    row = row_for(supplier("Certificaciones desconocidas"))

    assert row.certifications_score == 0.0


def test_confirmed_certifications_are_scored():
    row = row_for(
        supplier(
            "Proveedor certificado",
            certifications=["ISO 9001", "HACCP"],
            certifications_status="confirmado",
        )
    )

    assert row.certifications_score == 100.0


def test_supplier_without_sources_receives_zero_evidence_score():
    row = row_for(
        supplier(
            "Proveedor sin fuentes",
            confidence="alta",
        )
    )

    assert row.evidence_score == 0.0


def test_supplier_with_source_uses_confidence_for_evidence_score():
    source = Source(
        title="Fuente oficial",
        url="https://example.com/proveedor",
    )

    high = row_for(
        supplier(
            "Evidencia alta",
            confidence="alta",
            sources=[source],
        )
    )
    medium = row_for(
        supplier(
            "Evidencia media",
            confidence="media",
            sources=[source],
        )
    )
    low = row_for(
        supplier(
            "Evidencia baja",
            confidence="baja",
            sources=[source],
        )
    )

    assert high.evidence_score == 100.0
    assert medium.evidence_score == 70.0
    assert low.evidence_score == 40.0


def test_ranks_are_consecutive_starting_at_one():
    suppliers = [
        supplier("Proveedor A", total=100_000, price_status="confirmado"),
        supplier("Proveedor B", total=120_000, price_status="confirmado"),
        supplier("Proveedor C"),
    ]

    ranking = rank_suppliers(suppliers)

    assert [row.rank for row in ranking] == [1, 2, 3]


def test_estimated_price_is_discounted_for_uncertainty():
    confirmed = supplier(
        "Precio confirmado",
        total=100_000,
        price_status="confirmado",
    )
    estimated = supplier(
        "Precio estimado",
        total=100_000,
        price_status="estimado",
    )

    ranking = rank_suppliers([confirmed, estimated])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Precio confirmado"].price_score == 100.0
    assert rows["Precio estimado"].price_score == 80.0


def test_estimated_credit_is_discounted_for_uncertainty():
    confirmed = row_for(
        supplier(
            "Crédito confirmado",
            credit_days=30,
            credit_status="confirmado",
        )
    )
    estimated = row_for(
        supplier(
            "Crédito estimado",
            credit_days=30,
            credit_status="estimado",
        )
    )

    assert confirmed.credit_score == 80.0
    assert estimated.credit_score == 64.0


def test_estimated_delivery_is_discounted_for_uncertainty():
    confirmed = row_for(
        supplier(
            "Entrega confirmada",
            delivery_days=2,
            delivery_status="confirmado",
        )
    )
    estimated = row_for(
        supplier(
            "Entrega estimada",
            delivery_days=2,
            delivery_status="estimado",
        )
    )

    assert confirmed.delivery_score == 90.0
    assert estimated.delivery_score == 72.0


def test_estimated_certifications_are_discounted_for_uncertainty():
    confirmed = row_for(
        supplier(
            "Certificaciones confirmadas",
            certifications=["ISO 9001", "HACCP"],
            certifications_status="confirmado",
        )
    )
    estimated = row_for(
        supplier(
            "Certificaciones estimadas",
            certifications=["ISO 9001", "HACCP"],
            certifications_status="estimado",
        )
    )

    assert confirmed.certifications_score == 100.0
    assert estimated.certifications_score == 80.0


def test_unconfirmed_price_does_not_set_price_benchmark():
    confirmed = supplier(
        "Precio confirmado",
        total=100_000,
        price_status="confirmado",
    )
    unconfirmed = supplier(
        "Precio por confirmar",
        total=50_000,
        price_status="por_confirmar",
    )

    ranking = rank_suppliers([confirmed, unconfirmed])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Precio confirmado"].price_score == 100.0
    assert rows["Precio por confirmar"].price_score == 0.0
