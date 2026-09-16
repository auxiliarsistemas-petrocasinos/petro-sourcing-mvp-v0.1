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


def test_unit_prices_are_used_when_delivered_totals_are_missing():
    cheap = SupplierResearch(
        supplier_name="Proveedor exacto barato",
        product_match="Guantes nitrilo talla M sin polvo",
        product_match_status="confirmado",
        price_text="$16.000 COP por caja",
        price_cop_per_unit=16_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )

    expensive = SupplierResearch(
        supplier_name="Proveedor exacto caro",
        product_match="Guantes nitrilo talla M sin polvo",
        product_match_status="confirmado",
        price_text="$19.150 COP por caja",
        price_cop_per_unit=19_150,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )

    ranking = rank_suppliers([expensive, cheap])
    rows = {
        row.supplier.supplier_name: row
        for row in ranking
    }

    assert rows["Proveedor exacto barato"].price_score == 100.0
    assert rows["Proveedor exacto caro"].price_score == 83.6


def test_nonmatching_product_price_does_not_set_price_benchmark():
    exact = SupplierResearch(
        supplier_name="Talla M",
        product_match="Guantes nitrilo talla M sin polvo",
        product_match_status="confirmado",
        price_text="$16.000 COP",
        price_cop_per_unit=16_000,
        price_status="confirmado",
        evidence_summary="Coincidencia exacta.",
    )

    wrong_size = SupplierResearch(
        supplier_name="Talla S",
        product_match="Guantes nitrilo talla S sin polvo",
        product_match_status="estimado",
        price_text="$10.000 COP",
        price_cop_per_unit=10_000,
        price_status="confirmado",
        evidence_summary="La talla no coincide.",
    )

    ranking = rank_suppliers([wrong_size, exact])
    rows = {
        row.supplier.supplier_name: row
        for row in ranking
    }

    assert rows["Talla M"].price_score == 100.0
    assert rows["Talla S"].price_score == 0.0


def test_generic_epp_label_is_not_scored_as_certification():
    row = row_for(
        supplier(
            "Proveedor EPP",
            certifications=[
                "Elementos de Protección Personal (EPP)",
            ],
            certifications_status="confirmado",
        )
    )

    assert row.certifications_score == 0.0


def test_invima_registration_is_scored_as_certification():
    row = row_for(
        supplier(
            "Proveedor INVIMA",
            certifications=[
                "Registro Sanitario Colombia INVIMA 2018",
            ],
            certifications_status="confirmado",
        )
    )

    assert row.certifications_score == 80.0


def test_marketplace_does_not_score_or_set_price_benchmark():
    marketplace = supplier(
        "Marketplace",
        total=50_000,
        price_status="confirmado",
        credit_days=30,
        credit_status="confirmado",
        delivery_days=1,
        delivery_status="confirmado",
    )
    marketplace.supplier_type = (
        "Marketplace / Directorio de múltiples vendedores"
    )

    direct = supplier(
        "Proveedor directo",
        total=100_000,
        price_status="confirmado",
    )
    direct.supplier_type = "Distribuidor mayorista"

    ranking = rank_suppliers(
        [marketplace, direct]
    )
    rows = {
        row.supplier.supplier_name: row
        for row in ranking
    }

    assert rows["Marketplace"].score == 0.0
    assert rows["Marketplace"].price_score == 0.0

    assert rows["Proveedor directo"].price_score == 100.0
    assert (
        rows["Proveedor directo"].rank
        < rows["Marketplace"].rank
    )


def test_zero_credit_days_receives_zero_credit_score():
    row = row_for(
        supplier(
            "Pago de contado",
            credit_days=0,
            credit_status="confirmado",
        )
    )

    assert row.credit_score == 0.0




def test_third_party_financing_does_not_score_as_trade_credit():
    item = supplier(
        "Financiación externa",
        credit_days=30,
        credit_status="confirmado",
    )
    item.credit_terms = (
        "Financiación a 30 días con MercadoPago"
    )

    row = row_for(item)

    assert row.credit_score == 0.0


def test_card_installments_do_not_score_as_trade_credit():
    item = supplier(
        "Pago con tarjeta",
        credit_days=90,
        credit_status="confirmado",
    )
    item.credit_terms = (
        "3 cuotas sin interés con tarjeta de crédito"
    )

    row = row_for(item)

    assert row.credit_score == 0.0


def test_direct_trade_credit_still_scores():
    item = supplier(
        "Crédito proveedor",
        credit_days=30,
        credit_status="confirmado",
    )
    item.credit_terms = (
        "Crédito comercial directo a 30 días"
    )

    row = row_for(item)

    assert row.credit_score == 80.0


def test_unconfirmed_product_match_receives_zero_total_score():
    source = Source(
        title="Fuente oficial",
        url="https://example.com/proveedor",
    )

    item = supplier(
        "Producto no confirmado",
        total=50_000,
        price_status="confirmado",
        credit_days=60,
        credit_status="confirmado",
        delivery_days=1,
        delivery_status="confirmado",
        certifications=["ISO 9001"],
        certifications_status="confirmado",
        confidence="alta",
        sources=[source],
    )
    item.product_match_status = "por_confirmar"

    row = row_for(item)

    assert row.price_score == 0.0
    assert row.credit_score == 0.0
    assert row.delivery_score == 0.0
    assert row.certifications_score == 0.0
    assert row.evidence_score == 0.0
    assert row.score == 0.0


def test_estimated_product_match_receives_zero_total_score():
    source = Source(
        title="Fuente oficial",
        url="https://example.com/proveedor",
    )

    item = supplier(
        "Producto estimado",
        delivery_days=1,
        delivery_status="confirmado",
        confidence="alta",
        sources=[source],
    )
    item.product_match_status = "estimado"

    row = row_for(item)

    assert row.delivery_score == 0.0
    assert row.evidence_score == 0.0
    assert row.score == 0.0
