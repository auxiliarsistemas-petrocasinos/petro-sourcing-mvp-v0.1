from types import SimpleNamespace

from app import research
from app.models import ResearchResult, Source, SupplierResearch


def test_collect_url_annotations_deduplicates_sources():
    citation = SimpleNamespace(
        type="url_citation",
        url="https://proveedor.example/producto",
        title="Proveedor oficial",
    )
    duplicate = SimpleNamespace(
        type="url_citation",
        url="https://proveedor.example/producto",
        title="Proveedor oficial duplicado",
    )
    ignored = SimpleNamespace(
        type="other",
        url="https://ignorado.example",
        title="Ignorado",
    )

    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        annotations=[citation, duplicate, ignored],
                    )
                ],
            )
        ]
    )

    sources = research._collect_url_annotations(response)

    assert sources == [
        {
            "title": "Proveedor oficial",
            "url": "https://proveedor.example/producto",
        }
    ]


def test_evidence_policy_removes_sources_not_returned_by_search():
    supplier = SupplierResearch(
        supplier_name="Proveedor de prueba",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        price_text="$100.000",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        credit_days=30,
        credit_status="confirmado",
        delivery_days=2,
        delivery_status="confirmado",
        certifications=["ISO 9001"],
        certifications_status="confirmado",
        evidence_summary="Información aparentemente confirmada.",
        confidence="alta",
        sources=[
            Source(
                title="URL inventada",
                url="https://inventada.example/proveedor",
            )
        ],
    )

    result = ResearchResult(
        interpreted_request="Comprar producto",
        product="Producto",
        quantity="100 unidades",
        destination="Bogotá",
        suppliers=[supplier],
        recommendation_summary="Resumen",
    )

    validated = research._enforce_source_evidence(
        result,
        [
            {
                "title": "Fuente recuperada realmente",
                "url": "https://real.example/proveedor",
            }
        ],
    )

    checked = validated.suppliers[0]

    assert checked.sources == []
    assert checked.confidence == "baja"
    assert checked.price_status == "por_confirmar"
    assert checked.estimated_total_delivered_cop is None
    assert checked.credit_status == "por_confirmar"
    assert checked.credit_days is None
    assert checked.delivery_status == "por_confirmar"
    assert checked.delivery_days is None
    assert checked.certifications_status == "por_confirmar"
    assert checked.certifications == []


def test_evidence_policy_keeps_allowed_supplier_source():
    allowed = Source(
        title="Proveedor oficial",
        url="https://real.example/proveedor",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor real",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        evidence_summary="Proveedor respaldado por fuente.",
        confidence="alta",
        sources=[allowed],
    )

    result = ResearchResult(
        interpreted_request="Comprar producto",
        product="Producto",
        quantity="100 unidades",
        destination="Bogotá",
        suppliers=[supplier],
        recommendation_summary="Resumen",
    )

    validated = research._enforce_source_evidence(
        result,
        [
            {
                "title": "Proveedor oficial",
                "url": "https://real.example/proveedor",
            }
        ],
    )

    checked = validated.suppliers[0]

    assert checked.sources == [allowed]
    assert checked.confidence == "alta"
    assert checked.price_status == "confirmado"
    assert checked.estimated_total_delivered_cop == 100_000
