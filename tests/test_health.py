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
        pending_questions=[
            "Proveedor Uno tiene stock suficiente."
        ],
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

    pending = body["result"]["pending_questions"]

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

    assert (
        persisted["body"]["result"]["recommendation_summary"]
        == summary
    )
    assert (
        persisted["body"]["result"]["pending_questions"]
        == pending
    )
    assert persisted["body"]["raw_report"] == "Informe original."


def test_research_returns_503_when_gemini_is_temporarily_unavailable(
    monkeypatch,
):
    from google.genai import errors as genai_errors

    from app import main

    error = genai_errors.ServerError(
        503,
        {
            "error": {
                "message": "Service unavailable",
                "status": "UNAVAILABLE",
            }
        },
        None,
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
            "El proveedor de IA no está disponible temporalmente."
        )
    }


def test_research_returns_503_when_tavily_reaches_usage_limit(
    monkeypatch,
):
    from tavily.errors import UsageLimitExceededError

    from app import main

    def fail_research(_query):
        raise UsageLimitExceededError("Search limit reached")

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
            "El servicio de búsqueda no está disponible temporalmente."
        )
    }


def test_research_returns_503_when_tavily_times_out(
    monkeypatch,
):
    from tavily.errors import TimeoutError as TavilyTimeoutError

    from app import main

    def fail_research(_query):
        raise TavilyTimeoutError(30)

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
            "El servicio de búsqueda no está disponible temporalmente."
        )
    }


def test_research_returns_500_when_gemini_credentials_are_invalid(
    monkeypatch,
):
    from google.genai import errors as genai_errors

    from app import main

    error = genai_errors.ClientError(
        401,
        {
            "error": {
                "message": "Invalid API key",
                "status": "UNAUTHENTICATED",
            }
        },
        None,
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

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "La configuración del proveedor de IA no es válida."
        )
    }


def test_research_returns_500_when_tavily_api_key_is_invalid(
    monkeypatch,
):
    from tavily.errors import InvalidAPIKeyError

    from app import main

    def fail_research(_query):
        raise InvalidAPIKeyError("Invalid API key")

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

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "La configuración del servicio de búsqueda no es válida."
        )
    }



def test_research_returns_400_for_out_of_scope_request(
    monkeypatch,
):
    from app import main
    from app.research import InvalidPurchaseRequestError

    def reject_research(_query):
        raise InvalidPurchaseRequestError(
            "Este agente solo atiende solicitudes de "
            "abastecimiento. Indica qué producto o "
            "servicio necesitas comprar, cotizar "
            "o comparar."
        )

    monkeypatch.setattr(
        main,
        "research_purchase",
        reject_research,
    )

    response = client.post(
        "/api/research",
        json={
            "query": "Que paso el 26 de mayo de 1957?"
        },
    )

    assert response.status_code == 400
    assert (
        "solo atiende solicitudes de abastecimiento"
        in response.json()["detail"]
    )


def test_validating_reviewed_price_persists_and_recalculates_ranking(
    monkeypatch,
):
    from app import main
    from app.models import ResearchResult, SupplierResearch
    from app.scoring import rank_suppliers

    suspicious = SupplierResearch(
        supplier_name="Precio sospechoso",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=40_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )
    normal = SupplierResearch(
        supplier_name="Precio normal",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )
    high = SupplierResearch(
        supplier_name="Precio alto",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=105_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )

    result = ResearchResult(
        interpreted_request="Comprar producto.",
        product="Producto",
        quantity="1",
        destination="Bogotá",
        suppliers=[suspicious, normal, high],
        recommendation_summary="",
        pending_questions=[],
    )

    initial_ranking = rank_suppliers(result.suppliers)

    assert suspicious.price_review_status == "requires_review"

    stored_item = {
        "id": 77,
        "created_at": "2026-09-17T16:00:00+00:00",
        "query": "Necesito comprar un producto.",
        "result": {
            "result": result.model_dump(),
            "ranking": [
                row.model_dump()
                for row in initial_ranking
            ],
            "source_count": 0,
            "global_sources": [],
            "raw_report": "",
        },
    }

    persisted = {}

    def fake_get_research(research_id):
        if research_id != 77:
            return None
        return stored_item

    def fake_update_research(research_id, payload):
        persisted["research_id"] = research_id
        persisted["payload"] = payload
        stored_item["result"] = payload
        return True

    monkeypatch.setattr(
        main,
        "get_research",
        fake_get_research,
    )
    monkeypatch.setattr(
        main,
        "update_research",
        fake_update_research,
        raising=False,
    )

    response = client.patch(
        (
            "/api/research/77/suppliers/"
            "Precio%20sospechoso/price-review"
        ),
        json={"status": "validated"},
    )

    assert response.status_code == 200

    body = response.json()

    suppliers = {
        supplier["supplier_name"]: supplier
        for supplier in body["result"]["suppliers"]
    }
    ranking = {
        row["supplier"]["supplier_name"]: row
        for row in body["ranking"]
    }

    assert (
        suppliers["Precio sospechoso"]["price_review_status"]
        == "validated"
    )
    assert (
        suppliers["Precio sospechoso"]["price_review_reason"]
        is None
    )
    assert ranking["Precio sospechoso"]["price_score"] == 100.0

    assert persisted["research_id"] == 77

    reloaded = client.get("/api/history/77")

    assert reloaded.status_code == 200

    reloaded_suppliers = {
        supplier["supplier_name"]: supplier
        for supplier
        in reloaded.json()["result"]["result"]["suppliers"]
    }

    assert (
        reloaded_suppliers[
            "Precio sospechoso"
        ]["price_review_status"]
        == "validated"
    )


def test_price_validation_rejects_price_not_pending_review(
    monkeypatch,
):
    from app import main
    from app.models import ResearchResult, SupplierResearch

    supplier = SupplierResearch(
        supplier_name="Precio normal",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )

    result = ResearchResult(
        interpreted_request="Comprar producto.",
        product="Producto",
        quantity="1",
        destination="Bogotá",
        suppliers=[supplier],
        recommendation_summary="",
        pending_questions=[],
    )

    stored_item = {
        "id": 88,
        "created_at": "2026-09-17T16:00:00+00:00",
        "query": "Necesito comprar un producto.",
        "result": {
            "result": result.model_dump(),
            "ranking": [],
            "source_count": 0,
            "global_sources": [],
            "raw_report": "",
        },
    }

    monkeypatch.setattr(
        main,
        "get_research",
        lambda research_id: (
            stored_item if research_id == 88 else None
        ),
    )

    response = client.patch(
        (
            "/api/research/88/suppliers/"
            "Precio%20normal/price-review"
        ),
        json={"status": "validated"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "El precio del proveedor no está pendiente "
            "de validación."
        )
    }


def test_price_review_validation_records_and_preserves_timestamp(
    monkeypatch,
):
    from datetime import datetime

    from app import main
    from app.models import ResearchResult, SupplierResearch
    from app.scoring import rank_suppliers

    suspicious = SupplierResearch(
        supplier_name="Precio sospechoso",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=40_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )
    normal = SupplierResearch(
        supplier_name="Precio normal",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=100_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )
    high = SupplierResearch(
        supplier_name="Precio alto",
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=105_000,
        price_status="confirmado",
        evidence_summary="Precio confirmado.",
    )

    result = ResearchResult(
        interpreted_request="Comprar producto.",
        product="Producto",
        quantity="1",
        destination="Bogotá",
        suppliers=[suspicious, normal, high],
        recommendation_summary="",
        pending_questions=[],
    )

    ranking = rank_suppliers(result.suppliers)

    assert suspicious.price_review_status == "requires_review"

    stored_item = {
        "id": 91,
        "created_at": "2026-09-17T16:00:00+00:00",
        "query": "Necesito comprar un producto.",
        "result": {
            "result": result.model_dump(),
            "ranking": [
                row.model_dump()
                for row in ranking
            ],
            "source_count": 0,
            "global_sources": [],
            "raw_report": "",
        },
    }

    def fake_get_research(research_id):
        if research_id != 91:
            return None
        return stored_item

    def fake_update_research(research_id, payload):
        assert research_id == 91
        stored_item["result"] = payload
        return True

    monkeypatch.setattr(
        main,
        "get_research",
        fake_get_research,
    )
    monkeypatch.setattr(
        main,
        "update_research",
        fake_update_research,
    )

    first = client.patch(
        (
            "/api/research/91/suppliers/"
            "Precio%20sospechoso/price-review"
        ),
        json={"status": "validated"},
    )

    assert first.status_code == 200

    first_supplier = next(
        supplier
        for supplier in first.json()["result"]["suppliers"]
        if supplier["supplier_name"] == "Precio sospechoso"
    )

    timestamp = first_supplier["price_review_validated_at"]

    assert timestamp is not None

    parsed = datetime.fromisoformat(timestamp)

    assert parsed.tzinfo is not None

    second = client.patch(
        (
            "/api/research/91/suppliers/"
            "Precio%20sospechoso/price-review"
        ),
        json={"status": "validated"},
    )

    assert second.status_code == 200

    second_supplier = next(
        supplier
        for supplier in second.json()["result"]["suppliers"]
        if supplier["supplier_name"] == "Precio sospechoso"
    )

    assert (
        second_supplier["price_review_validated_at"]
        == timestamp
    )

    reloaded = client.get("/api/history/91")

    assert reloaded.status_code == 200

    persisted_supplier = next(
        supplier
        for supplier
        in reloaded.json()["result"]["result"]["suppliers"]
        if supplier["supplier_name"] == "Precio sospechoso"
    )

    assert (
        persisted_supplier["price_review_validated_at"]
        == timestamp
    )


def test_unvalidated_price_has_no_validation_timestamp():
    from app.models import SupplierResearch

    supplier = SupplierResearch(
        supplier_name="Proveedor normal",
        product_match="Producto solicitado",
        evidence_summary="Evidencia.",
    )

    assert supplier.price_review_status == "not_required"
    assert supplier.price_review_validated_at is None
