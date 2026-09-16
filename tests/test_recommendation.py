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
