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


def test_general_supplier_source_does_not_confirm_price_by_itself():
    allowed = Source(
        title="Proveedor oficial",
        url="https://real.example/proveedor",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor real",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        price_text="$100.000",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        evidence_summary="El proveedor existe, pero el precio no está sustentado.",
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
    assert checked.price_status == "por_confirmar"
    assert checked.price_text == "Por confirmar"
    assert checked.estimated_total_delivered_cop is None


def test_field_evidence_preserves_supported_commercial_claims():
    allowed = Source(
        title="Ficha comercial oficial",
        url="https://real.example/ficha-comercial",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor respaldado",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        price_text="$100.000",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        credit_terms="30 días",
        credit_days=30,
        credit_status="confirmado",
        delivery_time="2 días",
        delivery_days=2,
        delivery_status="confirmado",
        certifications=["ISO 9001"],
        certifications_status="confirmado",
        evidence_summary="Datos comerciales sustentados.",
        confidence="alta",
        sources=[allowed],
        price_sources=[allowed],
        credit_sources=[allowed],
        delivery_sources=[allowed],
        certifications_sources=[allowed],
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
                "title": "Ficha comercial oficial",
                "url": "https://real.example/ficha-comercial",
            }
        ],
    )

    checked = validated.suppliers[0]

    assert checked.price_sources == [allowed]
    assert checked.credit_sources == [allowed]
    assert checked.delivery_sources == [allowed]
    assert checked.certifications_sources == [allowed]

    assert checked.price_status == "confirmado"
    assert checked.estimated_total_delivered_cop == 100_000
    assert checked.credit_status == "confirmado"
    assert checked.credit_days == 30
    assert checked.delivery_status == "confirmado"
    assert checked.delivery_days == 2
    assert checked.certifications_status == "confirmado"
    assert checked.certifications == ["ISO 9001"]


def test_invalid_field_source_does_not_support_price_claim():
    general = Source(
        title="Proveedor oficial",
        url="https://real.example/proveedor",
    )
    invented_price_source = Source(
        title="Precio inventado",
        url="https://inventada.example/precio",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor mixto",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        price_text="$75.000",
        estimated_total_delivered_cop=75_000,
        price_status="confirmado",
        evidence_summary="Proveedor real con precio no sustentado.",
        confidence="alta",
        sources=[general],
        price_sources=[invented_price_source],
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

    assert checked.sources == [general]
    assert checked.price_sources == []
    assert checked.price_status == "por_confirmar"
    assert checked.price_text == "Por confirmar"
    assert checked.estimated_total_delivered_cop is None


def test_field_source_must_belong_to_same_supplier():
    supplier_source = Source(
        title="Proveedor A",
        url="https://a.example/proveedor",
    )
    other_supplier_price = Source(
        title="Precio proveedor B",
        url="https://b.example/precio",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor A",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        price_text="$90.000",
        estimated_total_delivered_cop=90_000,
        price_status="confirmado",
        evidence_summary="Proveedor A con una fuente de precio mal asociada.",
        confidence="alta",
        sources=[supplier_source],
        price_sources=[other_supplier_price],
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
                "title": "Proveedor A",
                "url": "https://a.example/proveedor",
            },
            {
                "title": "Precio proveedor B",
                "url": "https://b.example/precio",
            },
        ],
    )

    checked = validated.suppliers[0]

    assert checked.sources == [supplier_source]
    assert checked.price_sources == []
    assert checked.price_status == "por_confirmar"
    assert checked.estimated_total_delivered_cop is None


def test_general_supplier_source_does_not_confirm_capacity_or_contacts():
    general = Source(
        title="Proveedor oficial",
        url="https://real.example/proveedor",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor con datos no sustentados",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        capacity="10.000 unidades/mes",
        capacity_status="confirmado",
        phone="+57 300 123 4567",
        email="ventas@proveedor.example",
        website="https://proveedor.example",
        evidence_summary="Proveedor real, datos adicionales sin evidencia específica.",
        confidence="alta",
        sources=[general],
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

    assert checked.capacity == "Por confirmar"
    assert checked.capacity_status == "por_confirmar"
    assert checked.phone == "Por confirmar"
    assert checked.email == "Por confirmar"
    assert checked.website == "Por confirmar"


def test_specific_sources_preserve_capacity_and_contacts():
    general = Source(
        title="Proveedor oficial",
        url="https://real.example/proveedor",
    )
    capacity_source = Source(
        title="Ficha de capacidad",
        url="https://real.example/capacidad",
    )
    contact_source = Source(
        title="Contacto oficial",
        url="https://real.example/contacto",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor documentado",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        capacity="10.000 unidades/mes",
        capacity_status="confirmado",
        phone="+57 300 123 4567",
        email="ventas@proveedor.example",
        website="https://proveedor.example",
        evidence_summary="Capacidad y contactos documentados.",
        confidence="alta",
        sources=[general, capacity_source, contact_source],
        capacity_sources=[capacity_source],
        contact_sources=[contact_source],
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
            },
            {
                "title": "Ficha de capacidad",
                "url": "https://real.example/capacidad",
            },
            {
                "title": "Contacto oficial",
                "url": "https://real.example/contacto",
            },
        ],
    )

    checked = validated.suppliers[0]

    assert checked.capacity_sources == [capacity_source]
    assert checked.contact_sources == [contact_source]
    assert checked.capacity == "10.000 unidades/mes"
    assert checked.capacity_status == "confirmado"
    assert checked.phone == "+57 300 123 4567"
    assert checked.email == "ventas@proveedor.example"
    assert checked.website == "https://proveedor.example"


def test_contact_source_from_other_supplier_is_rejected():
    supplier_source = Source(
        title="Proveedor A",
        url="https://a.example/proveedor",
    )
    other_contact = Source(
        title="Contacto proveedor B",
        url="https://b.example/contacto",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor A",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        phone="+57 300 999 9999",
        email="ventas@b.example",
        website="https://b.example",
        evidence_summary="Contacto mal asociado.",
        confidence="alta",
        sources=[supplier_source],
        contact_sources=[other_contact],
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
                "title": "Proveedor A",
                "url": "https://a.example/proveedor",
            },
            {
                "title": "Contacto proveedor B",
                "url": "https://b.example/contacto",
            },
        ],
    )

    checked = validated.suppliers[0]

    assert checked.contact_sources == []
    assert checked.phone == "Por confirmar"
    assert checked.email == "Por confirmar"
    assert checked.website == "Por confirmar"
