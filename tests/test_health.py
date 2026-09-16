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
