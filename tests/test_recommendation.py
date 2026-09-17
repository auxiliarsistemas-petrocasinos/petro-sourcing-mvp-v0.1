from app.models import ResearchResult, Source, SupplierResearch
from app.recommendation import build_recommendation_summary
from app.scoring import rank_suppliers


def supplier(
    name: str,
    *,
    match_status: str = "confirmado",
    price_text: str = "Por confirmar",
    price: float | None = None,
    price_status: str = "por_confirmar",
    delivery_time: str = "Por confirmar",
    delivery_days: float | None = None,
    delivery_status: str = "por_confirmar",
    capacity_status: str = "por_confirmar",
) -> SupplierResearch:
    return SupplierResearch(
        supplier_name=name,
        product_match="Guantes nitrilo talla M sin polvo",
        product_match_status=match_status,
        price_text=price_text,
        price_cop_per_unit=price,
        price_status=price_status,
        delivery_time=delivery_time,
        delivery_days=delivery_days,
        delivery_status=delivery_status,
        capacity_status=capacity_status,
        evidence_summary="Evidencia de prueba.",
        confidence="alta",
        sources=[
            Source(
                title="Fuente",
                url=f"https://example.com/{name}",
            )
        ],
    )


def test_safe_summary_does_not_reuse_llm_stock_claim():
    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary=(
            "Proveedor Uno tiene stock suficiente para 100 cajas."
        ),
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "stock suficiente" not in summary.lower()
    assert "Proveedor Uno" in summary
    assert "$16.000 COP por caja" in summary
    assert "disponibilidad para 100 cajas" in summary


def test_safe_summary_prefers_confirmed_product_match():
    wrong_product = supplier(
        "Proveedor talla S",
        match_status="estimado",
        delivery_time="Entrega inmediata",
        delivery_days=1,
        delivery_status="confirmado",
    )

    exact_product = supplier(
        "Proveedor talla M",
        match_status="confirmado",
        price_text="$20.000 COP",
        price=20_000,
        price_status="confirmado",
    )

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[wrong_product, exact_product],
        recommendation_summary="Texto no confiable.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert summary.startswith("Proveedor talla M ")
    assert "Proveedor talla S encabeza" not in summary


def test_safe_summary_does_not_claim_unknown_price():
    top = supplier("Proveedor Uno")

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "precio reportado:" not in summary.lower()
    assert "costo total puesto en Bogotá" in summary


def test_safe_summary_still_confirms_requested_quantity_when_capacity_is_confirmed():
    top = supplier(
        "Proveedor Uno",
        price_text="$14.700 COP por caja",
        price=14_700,
        price_status="confirmado",
        capacity_status="confirmado",
    )
    top.capacity = "152 unidades en stock"

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "disponibilidad para 100 cajas" in summary


def test_pending_questions_replace_llm_claims():
    from app.recommendation import build_pending_questions

    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Resumen.",
        pending_questions=[
            "Proveedor Uno tiene stock suficiente."
        ],
    )

    ranking = rank_suppliers(result.suppliers)

    pending = build_pending_questions(
        result,
        ranking,
    )

    assert not any(
        "stock suficiente" in item.lower()
        for item in pending
    )
    assert (
        "Confirmar con Proveedor Uno disponibilidad "
        "para 100 cajas."
        in pending
    )
    assert (
        "Confirmar condiciones de crédito con Proveedor Uno."
        in pending
    )


def test_pending_questions_confirm_estimated_commercial_data():
    from app.recommendation import build_pending_questions

    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="estimado",
        delivery_time="1 a 2 días",
        delivery_days=2,
        delivery_status="estimado",
    )
    top.credit_terms = "30 días estimados"
    top.credit_status = "estimado"
    top.certifications = ["ISO 9001"]
    top.certifications_status = "estimado"
    top.estimated_total_delivered_cop = 1_600_000

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Resumen.",
    )

    ranking = rank_suppliers(result.suppliers)

    pending = build_pending_questions(
        result,
        ranking,
    )

    assert (
        "Confirmar precio vigente con Proveedor Uno."
        in pending
    )
    assert (
        "Confirmar condiciones de crédito con Proveedor Uno."
        in pending
    )
    assert (
        "Confirmar tiempo de entrega hasta Bogotá "
        "con Proveedor Uno."
        in pending
    )
    assert (
        "Confirmar certificaciones o documentos de calidad "
        "con Proveedor Uno."
        in pending
    )


def test_pending_questions_include_missing_request_data():
    from app.recommendation import build_pending_questions

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="Por confirmar",
        destination="Por confirmar",
        suppliers=[],
        recommendation_summary="Resumen.",
    )

    pending = build_pending_questions(
        result,
        [],
    )

    assert "¿Qué cantidad necesitas comprar?" in pending
    assert "¿Cuál es el destino de entrega?" in pending
    assert any(
        "ampliar la investigación" in item.lower()
        for item in pending
    )


def test_safe_summary_does_not_recommend_marketplace():
    marketplace = supplier(
        "Marketplace",
        price_text="$10.000 COP por caja",
        price=10_000,
        price_status="confirmado",
    )
    marketplace.supplier_type = (
        "Marketplace / Directorio de múltiples vendedores"
    )

    direct = supplier(
        "Proveedor Directo",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )
    direct.supplier_type = "Distribuidor mayorista"

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[marketplace, direct],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert summary.startswith("Proveedor Directo ")
    assert "Marketplace encabeza" not in summary


def test_pending_questions_target_direct_supplier_not_marketplace():
    from app.recommendation import build_pending_questions

    marketplace = supplier(
        "Marketplace",
        price_text="$10.000 COP por caja",
        price=10_000,
        price_status="confirmado",
    )
    marketplace.supplier_type = "Marketplace"

    direct = supplier(
        "Proveedor Directo",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )
    direct.supplier_type = "Fabricante"

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[marketplace, direct],
        recommendation_summary="Resumen.",
    )

    ranking = rank_suppliers(result.suppliers)

    pending = build_pending_questions(
        result,
        ranking,
    )

    assert any(
        "Proveedor Directo" in item
        for item in pending
    )
    assert not any(
        "Marketplace" in item
        for item in pending
    )


def test_recommendation_skips_confirmed_out_of_stock_supplier():
    unavailable = supplier(
        "Proveedor agotado",
        price_text="$10.000 COP",
        price=10_000,
        price_status="confirmado",
        delivery_time="Entrega inmediata",
        delivery_days=1,
        delivery_status="confirmado",
    )
    unavailable.availability_text = "Agotado"
    unavailable.availability_status = "sin_stock"

    usable = supplier(
        "Proveedor utilizable",
        delivery_time="2 días",
        delivery_days=2,
        delivery_status="confirmado",
    )

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[unavailable, usable],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert summary.startswith(
        "Proveedor utilizable "
    )
    assert "Proveedor agotado encabeza" not in summary


def test_recommendation_skips_insufficient_stock_supplier():
    insufficient = supplier(
        "Proveedor insuficiente",
        price_text="$15.000 COP",
        price=15_000,
        price_status="confirmado",
    )
    insufficient.availability_status = "disponible"
    insufficient.fulfillment_status = "insuficiente"

    usable = supplier(
        "Proveedor utilizable",
    )

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[insufficient, usable],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert summary.startswith("Proveedor utilizable ")
    assert "Proveedor insuficiente encabeza" not in summary


def price_review_scenario():
    suspicious = supplier(
        "Precio sospechoso",
        price_text="$40.000 COP",
        price=40_000,
        price_status="confirmado",
    )
    suspicious.estimated_total_delivered_cop = 40_000

    normal = supplier(
        "Precio normal",
        price_text="$100.000 COP",
        price=100_000,
        price_status="confirmado",
    )
    normal.estimated_total_delivered_cop = 100_000

    high = supplier(
        "Precio alto",
        price_text="$105.000 COP",
        price=105_000,
        price_status="confirmado",
    )
    high.estimated_total_delivered_cop = 105_000

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[suspicious, normal, high],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    assert suspicious.price_review_status == "requires_review"

    return result, ranking, suspicious


def test_summary_explains_price_requiring_review():
    result, ranking, _ = price_review_scenario()

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "Precio sospechoso" in summary
    assert "$40.000 COP" in summary
    assert "requiere validación" in summary
    assert "no se usa como referencia automática" in summary


def test_pending_questions_include_price_review_validation():
    from app.recommendation import build_pending_questions

    result, ranking, _ = price_review_scenario()

    pending = build_pending_questions(
        result,
        ranking,
    )

    assert (
        "Validar el precio reportado por Precio sospechoso "
        "antes de usarlo como referencia de precio."
        in pending
    )


def test_validated_price_no_longer_generates_review_warning():
    from app.recommendation import build_pending_questions

    result, _, suspicious = price_review_scenario()

    suspicious.price_review_status = "validated"
    suspicious.price_review_reason = None

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )
    pending = build_pending_questions(
        result,
        ranking,
    )

    assert "requiere validación" not in summary
    assert "no se usa como referencia automática" not in summary
    assert not any(
        "Validar el precio reportado por Precio sospechoso"
        in item
        for item in pending
    )


def test_summary_warns_when_recommended_supplier_has_low_confidence():
    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )
    top.confidence = "baja"

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "Proveedor Uno" in summary
    assert "confianza baja" in summary.lower()
    assert "antes de adjudicar" in summary.lower()


def test_summary_warns_when_recommended_supplier_has_no_sources():
    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )
    top.sources = []

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Texto previo.",
    )

    ranking = rank_suppliers(result.suppliers)

    summary = build_recommendation_summary(
        result,
        ranking,
    )

    assert "Proveedor Uno" in summary
    assert "fuentes" in summary.lower()
    assert "antes de adjudicar" in summary.lower()


def test_pending_questions_require_stronger_evidence_for_weak_recommendation():
    from app.recommendation import build_pending_questions

    top = supplier(
        "Proveedor Uno",
        price_text="$16.000 COP por caja",
        price=16_000,
        price_status="confirmado",
    )
    top.confidence = "baja"

    result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[top],
        recommendation_summary="Resumen.",
    )

    ranking = rank_suppliers(result.suppliers)

    pending = build_pending_questions(
        result,
        ranking,
    )

    assert any(
        "reforzar la evidencia" in item.lower()
        and "Proveedor Uno" in item
        for item in pending
    )
