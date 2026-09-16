from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_research_returns_503_when_ai_provider_is_rate_limited(
    monkeypatch,
):
    import httpx
    from openai import RateLimitError

    from app import main

    request = httpx.Request(
        "POST",
        "https://api.groq.com/openai/v1/responses",
    )
    upstream_response = httpx.Response(
        429,
        headers={"retry-after": "60"},
        request=request,
    )

    error = RateLimitError(
        "Rate limit reached",
        response=upstream_response,
        body={
            "error": {
                "type": "tokens",
                "code": "rate_limit_exceeded",
            }
        },
    )

    def fail_research(_query):
        raise error

    monkeypatch.setattr(
        main,
        "research_purchase",
        fail_research,
    )

    response = client.post(
        "/api/research",
        json={
            "query": (
                "Necesito comprar 100 cajas de guantes "
                "de nitrilo en Bogotá."
            )
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "El proveedor de IA alcanzó temporalmente "
            "su límite de uso."
        )
    }
    assert response.headers["retry-after"] == "60"


def test_research_replaces_llm_summary_before_response_and_persistence(
    monkeypatch,
):
    from app import main
    from app.models import ResearchResult, Source, SupplierResearch

    source = Source(
        title="Fuente oficial",
        url="https://example.com/proveedor",
    )

    supplier = SupplierResearch(
        supplier_name="Proveedor Uno",
        product_match="Guantes nitrilo talla M sin polvo",
        product_match_status="confirmado",
        price_text="$16.000 COP por caja",
        price_cop_per_unit=16_000,
        price_status="confirmado",
        capacity_status="por_confirmar",
        evidence_summary="Evidencia confirmada.",
        confidence="alta",
        sources=[source],
        price_sources=[source],
    )

    unsafe_result = ResearchResult(
        interpreted_request="Comprar guantes.",
        product="guantes de nitrilo",
        quantity="100 cajas",
        destination="Bogotá",
        suppliers=[supplier],
        recommendation_summary=(
            "Proveedor Uno tiene stock suficiente para 100 cajas."
        ),
    )

    def fake_research(_query):
        return (
            unsafe_result,
            [
                {
                    "title": source.title,
                    "url": source.url,
                }
            ],
            "Informe original.",
        )

    persisted = {}

    def fake_save_research(query, body):
        persisted["query"] = query
        persisted["body"] = body
        return 123

    monkeypatch.setattr(
        main,
        "research_purchase",
        fake_research,
    )
    monkeypatch.setattr(
        main,
        "save_research",
        fake_save_research,
    )

    response = client.post(
        "/api/research",
        json={
            "query": (
                "Necesito comprar 100 cajas de guantes "
                "de nitrilo talla M sin polvo en Bogotá."
            )
        },
    )

    assert response.status_code == 200

    body = response.json()
    summary = body["result"]["recommendation_summary"]

    assert body["research_id"] == 123
    assert "stock suficiente" not in summary.lower()
    assert "Proveedor Uno" in summary
    assert "$16.000 COP por caja" in summary
    assert "disponibilidad para 100 cajas" in summary

    assert (
        persisted["body"]["result"]["recommendation_summary"]
        == summary
    )
    assert persisted["body"]["raw_report"] == "Informe original."
