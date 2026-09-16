from types import SimpleNamespace

import pytest

from app import models, research
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



def test_purchase_brief_preserves_explicit_request_facts():
    intent = models.PurchaseRequestInterpretation(
        interpreted_request=(
            "Comprar 100 cajas de guantes de nitrilo talla M "
            "para entrega en Bogotá."
        ),
        product="Guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        required_specifications=["Talla M", "Sin polvo"],
    )

    brief = research._build_research_brief(intent)

    assert "Guantes de nitrilo" in brief
    assert "100 cajas" in brief
    assert "Bogotá" in brief
    assert "Talla M" in brief
    assert "Sin polvo" in brief


def test_purchase_brief_marks_missing_facts_without_inventing_them():
    intent = models.PurchaseRequestInterpretation(
        interpreted_request="Comprar guantes de nitrilo.",
        product="Guantes de nitrilo",
        quantity=None,
        destination=None,
    )

    brief = research._build_research_brief(intent)

    assert "Producto: Guantes de nitrilo" in brief
    assert "Cantidad: POR CONFIRMAR" in brief
    assert "Destino: POR CONFIRMAR" in brief


def test_purchase_interpretation_controls_final_request_fields():
    intent = models.PurchaseRequestInterpretation(
        interpreted_request=(
            "Comprar 100 cajas de guantes de nitrilo "
            "para entrega en Bogotá."
        ),
        product="Guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        required_specifications=["Talla M"],
    )

    result = ResearchResult(
        interpreted_request="Interpretación posterior incorrecta",
        product="Guantes de látex",
        quantity="500 cajas",
        destination="Medellín",
        required_specifications=["Talla XL"],
        suppliers=[],
        recommendation_summary="Resumen",
    )

    normalized = research._apply_purchase_interpretation(result, intent)

    assert normalized.interpreted_request == intent.interpreted_request
    assert normalized.product == "Guantes de nitrilo"
    assert normalized.quantity == "100 cajas"
    assert normalized.destination == "Bogotá"
    assert normalized.required_specifications == ["Talla M"]


def test_missing_purchase_facts_become_pending_questions():
    intent = models.PurchaseRequestInterpretation(
        interpreted_request="Comprar guantes de nitrilo.",
        product="Guantes de nitrilo",
        quantity=None,
        destination=None,
    )

    result = ResearchResult(
        interpreted_request="Temporal",
        product="Temporal",
        quantity="Temporal",
        destination="Temporal",
        suppliers=[],
        recommendation_summary="Resumen",
    )

    normalized = research._apply_purchase_interpretation(result, intent)

    assert normalized.quantity == "Por confirmar"
    assert normalized.destination == "Por confirmar"
    assert "¿Qué cantidad necesitas comprar?" in normalized.pending_questions
    assert "¿Cuál es el destino de entrega?" in normalized.pending_questions


def test_research_purchase_interprets_request_before_web_research(
    monkeypatch,
):
    intent = models.PurchaseRequestInterpretation(
        interpreted_request=(
            "Comprar 100 cajas de guantes de nitrilo "
            "para entrega en Bogotá."
        ),
        product="Guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        required_specifications=["Talla M"],
    )

    extracted_result = ResearchResult(
        interpreted_request="No debe prevalecer",
        product="Otro producto",
        quantity="Otra cantidad",
        destination="Otro destino",
        suppliers=[],
        recommendation_summary="Resumen",
    )

    events = []

    class FakeResponses:
        def parse(self, *, model, input, text_format):
            events.append(("parse", text_format))

            if text_format is models.PurchaseRequestInterpretation:
                return SimpleNamespace(output_parsed=intent)

            if text_format is ResearchResult:
                return SimpleNamespace(output_parsed=extracted_result)

            raise AssertionError(f"Formato inesperado: {text_format}")

        def create(self, *, model, reasoning, tools, input):
            events.append(("research", input))

            user_message = input[1]["content"]

            assert "Producto: Guantes de nitrilo" in user_message
            assert "Cantidad: 100 cajas" in user_message
            assert "Destino: Bogotá" in user_message
            assert "Talla M" in user_message

            return SimpleNamespace(
                output_text="Informe de investigación",
                output=[],
            )

    fake_client = SimpleNamespace(
        responses=FakeResponses(),
    )

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("SEARCH_PROVIDER", "native")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        research,
        "OpenAI",
        lambda api_key: fake_client,
    )

    result, sources, report = research.research_purchase(
        "Necesito 100 cajas de guantes de nitrilo talla M en Bogotá."
    )

    assert events[0] == (
        "parse",
        models.PurchaseRequestInterpretation,
    )
    assert events[1][0] == "research"
    assert events[2] == ("parse", ResearchResult)

    assert result.product == "Guantes de nitrilo"
    assert result.quantity == "100 cajas"
    assert result.destination == "Bogotá"
    assert result.required_specifications == ["Talla M"]

    assert sources == []
    assert report == "Informe de investigación"



def test_collect_url_annotations_supports_groq_browser_open():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="mcp_call",
                name="browser.search",
                output=(
                    "L0:\n"
                    "L1: URL: https://exa.ai/search?q=proveedores\n"
                    "L2: # Search Results\n"
                ),
            ),
            SimpleNamespace(
                type="mcp_call",
                name="browser.open",
                output=(
                    "L0:\n"
                    "L1: URL: https://hidalguantes.com/\n"
                    "L2: Guantes Industriales y de Seguridad en Colombia | "
                    "Hidalguantes\n"
                    "L3:\n"
                    "L4: Contenido del proveedor\n"
                ),
            ),
            SimpleNamespace(
                type="mcp_call",
                name="browser.open",
                output=(
                    "L0:\n"
                    "L1: URL: https://www.gudescol.com/\n"
                    "L2: Gudescol – Empresa de productos desechables\n"
                ),
            ),
        ]
    )

    sources = research._collect_url_annotations(response)

    assert sources == [
        {
            "title": (
                "Guantes Industriales y de Seguridad en Colombia | "
                "Hidalguantes"
            ),
            "url": "https://hidalguantes.com/",
        },
        {
            "title": "Gudescol – Empresa de productos desechables",
            "url": "https://www.gudescol.com/",
        },
    ]



def test_load_ai_config_supports_groq(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("SEARCH_PROVIDER", "native")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv(
        "GROQ_INTERPRET_MODEL",
        "openai/gpt-oss-20b",
    )
    monkeypatch.setenv(
        "GROQ_RESEARCH_MODEL",
        "openai/gpt-oss-20b",
    )
    monkeypatch.setenv(
        "GROQ_EXTRACT_MODEL",
        "openai/gpt-oss-20b",
    )

    config = research._load_ai_config()

    assert config.provider == "groq"
    assert config.api_key == "groq-test-key"
    assert config.base_url == "https://api.groq.com/openai/v1"
    assert config.interpret_model == "openai/gpt-oss-20b"
    assert config.research_model == "openai/gpt-oss-20b"
    assert config.extract_model == "openai/gpt-oss-20b"
    assert config.search_tool == {"type": "browser_search"}


def test_load_ai_config_preserves_openai_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv(
        "OPENAI_RESEARCH_MODEL",
        "gpt-5.6-terra",
    )
    monkeypatch.setenv(
        "OPENAI_EXTRACT_MODEL",
        "gpt-5.6-luna",
    )

    config = research._load_ai_config()

    assert config.provider == "openai"
    assert config.api_key == "openai-test-key"
    assert config.base_url is None
    assert config.interpret_model == "gpt-5.6-luna"
    assert config.research_model == "gpt-5.6-terra"
    assert config.extract_model == "gpt-5.6-luna"
    assert config.search_tool == {
        "type": "web_search",
        "search_context_size": "high",
    }


def test_load_ai_config_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "desconocido")

    with pytest.raises(
        RuntimeError,
        match="AI_PROVIDER no soportado",
    ):
        research._load_ai_config()


def test_load_ai_config_requires_groq_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="GROQ_API_KEY",
    ):
        research._load_ai_config()


def test_research_purchase_uses_groq_provider_config(monkeypatch):
    intent = models.PurchaseRequestInterpretation(
        interpreted_request="Comprar 100 cajas de guantes de nitrilo.",
        product="Guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
    )

    extracted_result = ResearchResult(
        interpreted_request="Temporal",
        product="Temporal",
        quantity="Temporal",
        destination="Temporal",
        suppliers=[],
        recommendation_summary="Resumen",
    )

    created_clients = []
    research_calls = []

    class FakeResponses:
        def parse(self, *, model, input, text_format):
            if text_format is models.PurchaseRequestInterpretation:
                return SimpleNamespace(output_parsed=intent)

            if text_format is ResearchResult:
                return SimpleNamespace(output_parsed=extracted_result)

            raise AssertionError(f"Formato inesperado: {text_format}")

        def create(self, **kwargs):
            research_calls.append(kwargs)

            return SimpleNamespace(
                output_text="Informe",
                output=[],
            )

    def fake_openai(**kwargs):
        created_clients.append(kwargs)
        return SimpleNamespace(
            responses=FakeResponses(),
        )

    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("SEARCH_PROVIDER", "native")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv(
        "GROQ_INTERPRET_MODEL",
        "openai/gpt-oss-20b",
    )
    monkeypatch.setenv(
        "GROQ_RESEARCH_MODEL",
        "openai/gpt-oss-20b",
    )
    monkeypatch.setenv(
        "GROQ_EXTRACT_MODEL",
        "openai/gpt-oss-20b",
    )
    monkeypatch.setattr(
        research,
        "OpenAI",
        fake_openai,
    )

    result, _, _ = research.research_purchase(
        "Necesito 100 cajas de guantes de nitrilo en Bogotá."
    )

    assert created_clients == [
        {
            "api_key": "groq-test-key",
            "base_url": "https://api.groq.com/openai/v1",
        }
    ]

    assert research_calls[0]["model"] == "openai/gpt-oss-20b"
    assert research_calls[0]["tools"] == [
        {
            "type": "browser_search",
        }
    ]

    assert result.product == "Guantes de nitrilo"
    assert result.quantity == "100 cajas"
    assert result.destination == "Bogotá"


def test_load_ai_config_supports_gemini(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv(
        "GEMINI_INTERPRET_MODEL",
        "gemini-3.6-flash",
    )
    monkeypatch.setenv(
        "GEMINI_RESEARCH_MODEL",
        "gemini-3.6-flash",
    )
    monkeypatch.setenv(
        "GEMINI_EXTRACT_MODEL",
        "gemini-3.6-flash",
    )

    config = research._load_ai_config()

    assert config.provider == "gemini"
    assert config.api_key == "gemini-test-key"
    assert config.base_url is None
    assert config.interpret_model == "gemini-3.6-flash"
    assert config.research_model == "gemini-3.6-flash"
    assert config.extract_model == "gemini-3.6-flash"


def test_load_ai_config_requires_gemini_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="GEMINI_API_KEY",
    ):
        research._load_ai_config()


def test_load_search_config_supports_tavily(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")

    config = research._load_search_config()

    assert config.provider == "tavily"
    assert config.api_key == "tavily-test-key"


def test_load_search_config_supports_native(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "native")

    config = research._load_search_config()

    assert config.provider == "native"
    assert config.api_key is None


def test_load_search_config_requires_tavily_key(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="TAVILY_API_KEY",
    ):
        research._load_search_config()


def test_load_search_config_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "desconocido")

    with pytest.raises(
        RuntimeError,
        match="SEARCH_PROVIDER no soportado",
    ):
        research._load_search_config()


def test_search_with_tavily_collects_sources_and_evidence(
    monkeypatch,
):
    created_clients = []
    search_calls = []

    class FakeTavilyClient:
        def __init__(self, *, api_key):
            created_clients.append(api_key)

        def search(self, **kwargs):
            search_calls.append(kwargs)

            return {
                "results": [
                    {
                        "title": "Proveedor Uno",
                        "url": "https://proveedor-uno.example/producto",
                        "content": (
                            "Guantes de nitrilo talla M sin polvo. "
                            "Entrega disponible en Bogotá."
                        ),
                    },
                    {
                        "title": "Proveedor Dos",
                        "url": "https://proveedor-dos.example/",
                        "content": (
                            "Distribuidor colombiano de elementos "
                            "de protección."
                        ),
                    },
                    {
                        "title": "Duplicado",
                        "url": "https://proveedor-uno.example/producto",
                        "content": "Contenido repetido.",
                    },
                    {
                        "title": "Sin URL",
                        "url": "",
                        "content": "No debe utilizarse.",
                    },
                ]
            }

    monkeypatch.setattr(
        research,
        "TavilyClient",
        FakeTavilyClient,
        raising=False,
    )

    sources, evidence = research._search_with_tavily(
        query="proveedores guantes nitrilo Colombia",
        api_key="tavily-test-key",
        max_results=8,
    )

    assert created_clients == ["tavily-test-key"]

    assert search_calls == [
        {
            "query": "proveedores guantes nitrilo Colombia",
            "max_results": 8,
            "search_depth": "basic",
            "topic": "general",
            "country": "colombia",
        }
    ]

    assert sources == [
        {
            "title": "Proveedor Uno",
            "url": "https://proveedor-uno.example/producto",
        },
        {
            "title": "Proveedor Dos",
            "url": "https://proveedor-dos.example/",
        },
    ]

    assert "FUENTE 1" in evidence
    assert "Proveedor Uno" in evidence
    assert "https://proveedor-uno.example/producto" in evidence
    assert "Guantes de nitrilo talla M sin polvo." in evidence

    assert "FUENTE 2" in evidence
    assert "Proveedor Dos" in evidence
    assert "https://proveedor-dos.example/" in evidence

    assert "Contenido repetido." not in evidence
    assert "No debe utilizarse." not in evidence


def test_search_with_tavily_rejects_empty_results(
    monkeypatch,
):
    class FakeTavilyClient:
        def __init__(self, *, api_key):
            pass

        def search(self, **kwargs):
            return {"results": []}

    monkeypatch.setattr(
        research,
        "TavilyClient",
        FakeTavilyClient,
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="Tavily no devolvió resultados",
    ):
        research._search_with_tavily(
            query="producto inexistente",
            api_key="tavily-test-key",
        )


def test_interpret_purchase_request_with_gemini_uses_structured_output():
    expected = models.PurchaseRequestInterpretation(
        interpreted_request=(
            "Comprar 100 cajas de guantes de nitrilo "
            "para entrega en Bogotá."
        ),
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        required_specifications=["talla M", "sin polvo"],
    )

    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(parsed=expected)

    client = SimpleNamespace(models=FakeModels())

    result = research._interpret_purchase_request_gemini(
        client,
        (
            "Necesito 100 cajas de guantes de nitrilo "
            "talla M sin polvo en Bogotá."
        ),
        "gemini-test-model",
    )

    assert result == expected
    assert calls[0]["model"] == "gemini-test-model"
    assert "100 cajas" in calls[0]["contents"]
    assert (
        calls[0]["config"].response_schema
        is models.PurchaseRequestInterpretation
    )


def test_extract_research_result_with_gemini_uses_sources():
    expected = ResearchResult(
        interpreted_request="Comprar guantes",
        product="Guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[],
        recommendation_summary="Resumen",
    )

    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(parsed=expected)

    client = SimpleNamespace(models=FakeModels())

    result = research._extract_research_result_gemini(
        client=client,
        report="Informe sustentado.",
        sources=[
            {
                "title": "Proveedor Uno",
                "url": "https://proveedor-uno.example/",
            }
        ],
        model="gemini-test-model",
    )

    assert result == expected
    assert calls[0]["model"] == "gemini-test-model"

    contents = calls[0]["contents"]
    assert "Informe sustentado." in contents
    assert "Proveedor Uno" in contents
    assert "https://proveedor-uno.example/" in contents

    assert calls[0]["config"].response_schema is ResearchResult


def test_research_purchase_uses_gemini_with_tavily(
    monkeypatch,
):
    intent = models.PurchaseRequestInterpretation(
        interpreted_request=(
            "Comprar 100 cajas de guantes de nitrilo "
            "para entrega en Bogotá."
        ),
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        required_specifications=["talla M", "sin polvo"],
    )

    extracted = ResearchResult(
        interpreted_request="Temporal",
        product="Temporal",
        quantity="Temporal",
        destination="Temporal",
        suppliers=[],
        recommendation_summary="Resumen Gemini",
    )

    gemini_keys = []
    model_calls = []
    tavily_calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            model_calls.append(kwargs)

            config = kwargs.get("config")
            schema = getattr(config, "response_schema", None)

            if schema is models.PurchaseRequestInterpretation:
                return SimpleNamespace(
                    parsed=intent,
                    text=None,
                )

            if schema is ResearchResult:
                return SimpleNamespace(
                    parsed=extracted,
                    text=None,
                )

            return SimpleNamespace(
                parsed=None,
                text="Informe de investigación sustentado.",
            )

    class FakeGeminiClient:
        def __init__(self, *, api_key):
            gemini_keys.append(api_key)
            self.models = FakeModels()

    def fake_tavily_search(
        query,
        api_key,
        max_results=8,
    ):
        tavily_calls.append(
            {
                "query": query,
                "api_key": api_key,
                "max_results": max_results,
            }
        )

        return (
            [
                {
                    "title": "Proveedor Uno",
                    "url": "https://proveedor-uno.example/",
                }
            ],
            (
                "FUENTE 1\n"
                "Título: Proveedor Uno\n"
                "URL: https://proveedor-uno.example/\n"
                "Contenido: Guantes de nitrilo."
            ),
        )

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv(
        "GEMINI_INTERPRET_MODEL",
        "gemini-3.6-flash",
    )
    monkeypatch.setenv(
        "GEMINI_RESEARCH_MODEL",
        "gemini-3.6-flash",
    )
    monkeypatch.setenv(
        "GEMINI_EXTRACT_MODEL",
        "gemini-3.6-flash",
    )
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")

    monkeypatch.setattr(
        research.genai,
        "Client",
        FakeGeminiClient,
    )
    monkeypatch.setattr(
        research,
        "_search_with_tavily",
        fake_tavily_search,
    )

    def forbidden_openai(**kwargs):
        raise AssertionError(
            "Gemini no debe crear un cliente OpenAI."
        )

    monkeypatch.setattr(
        research,
        "OpenAI",
        forbidden_openai,
    )

    result, sources, report = research.research_purchase(

            "Necesito 100 cajas de guantes de nitrilo "
            "talla M sin polvo para Bogotá."

    )

    assert gemini_keys == ["gemini-test-key"]

    assert len(tavily_calls) == 1
    assert tavily_calls[0]["api_key"] == "tavily-test-key"
    assert "guantes de nitrilo" in tavily_calls[0]["query"].lower()

    assert sources == [
        {
            "title": "Proveedor Uno",
            "url": "https://proveedor-uno.example/",
        }
    ]

    assert report == "Informe de investigación sustentado."

    assert result.product == "guantes de nitrilo"
    assert result.quantity == "100 cajas"
    assert result.destination == "Bogotá"

    assert len(model_calls) == 3
