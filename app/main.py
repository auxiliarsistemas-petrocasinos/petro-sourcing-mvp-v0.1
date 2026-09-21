from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.genai import errors as genai_errors
from openai import RateLimitError
from pydantic import BaseModel
from tavily.errors import ForbiddenError, InvalidAPIKeyError, UsageLimitExceededError
from tavily.errors import TimeoutError as TavilyTimeoutError

from .db import (
    get_research,
    init_db,
    list_research,
    save_research,
    update_research,
)
from .models import ResearchResult
from .recommendation import (
    build_pending_questions,
    build_recommendation_summary,
)
from .research import (
    InvalidPurchaseRequestError,
    research_purchase,
)
from .scoring import rank_suppliers

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Agente de Abastecimiento",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class ResearchRequest(BaseModel):
    query: str


class PriceReviewRequest(BaseModel):
    status: str


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/research")
def run_research(payload: ResearchRequest):
    query = payload.query.strip()
    if len(query) < 10:
        raise HTTPException(status_code=400, detail="Describe mejor la necesidad de compra.")

    try:
        result, global_sources, raw_report = research_purchase(query)
        ranking = rank_suppliers(result.suppliers)
        result.recommendation_summary = build_recommendation_summary(
            result,
            ranking,
        )
        result.pending_questions = build_pending_questions(
            result,
            ranking,
        )

        body = {
            "result": result.model_dump(),
            "ranking": [r.model_dump() for r in ranking],
            "source_count": len(global_sources),
            "global_sources": global_sources,
            "raw_report": raw_report,
        }
        research_id = save_research(query, body)
        return {"research_id": research_id, **body}
    except InvalidPurchaseRequestError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after")
        headers = (
            {"Retry-After": retry_after}
            if retry_after
            else None
        )

        logger.warning(
            "Proveedor de IA alcanzó límite de uso "
            "(retry_after=%s).",
            retry_after or "no informado",
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "El proveedor de IA alcanzó temporalmente "
                "su límite de uso."
            ),
            headers=headers,
        ) from exc
    except genai_errors.APIError as exc:
        logger.warning(
            "Error de API de Gemini "
            "(type=%s, code=%s).",
            type(exc).__name__,
            getattr(exc, "code", None),
        )

        if exc.code in {401, 403}:
            raise HTTPException(
                status_code=500,
                detail=(
                    "La configuración del proveedor de IA "
                    "no es válida."
                ),
            ) from exc

        if exc.code in {408, 429, 500, 502, 503, 504}:
            raise HTTPException(
                status_code=503,
                detail=(
                    "El proveedor de IA no está disponible "
                    "temporalmente."
                ),
            ) from exc

        raise

    except (
        InvalidAPIKeyError,
        ForbiddenError,
    ) as exc:
        logger.error(
            "Error de configuración o autorización "
            "del servicio de búsqueda (type=%s).",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "La configuración del servicio de búsqueda "
                "no es válida."
            ),
        ) from exc

    except (
        UsageLimitExceededError,
        TavilyTimeoutError,
    ) as exc:
        logger.warning(
            "Servicio de búsqueda temporalmente "
            "no disponible (type=%s).",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "El servicio de búsqueda no está disponible "
                "temporalmente."
            ),
        ) from exc

    except RuntimeError as exc:
        logger.exception(
            "Error de ejecución durante la investigación."
        )
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Error inesperado durante la investigación "
            "(type=%s).",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Ocurrió un error interno durante "
                "la investigación."
            ),
        ) from exc


@app.patch(
    "/api/research/{research_id}/suppliers/"
    "{supplier_name}/price-review"
)
def update_supplier_price_review(
    research_id: int,
    supplier_name: str,
    payload: PriceReviewRequest,
):
    if payload.status not in {
        "validated",
        "requires_review",
    }:
        raise HTTPException(
            status_code=422,
            detail="Estado de revisión de precio no soportado.",
        )

    item = get_research(research_id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Investigación no encontrada.",
        )

    body = item["result"]
    result = ResearchResult.model_validate(
        body["result"]
    )

    matches = [
        supplier
        for supplier in result.suppliers
        if supplier.supplier_name == supplier_name
    ]

    if not matches:
        raise HTTPException(
            status_code=404,
            detail="Proveedor no encontrado.",
        )

    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "El nombre del proveedor no identifica "
                "un único resultado."
            ),
        )

    supplier = matches[0]

    if payload.status == "validated":
        if supplier.price_review_status not in {
            "requires_review",
            "validated",
        }:
            raise HTTPException(
                status_code=409,
                detail=(
                    "El precio del proveedor no está pendiente "
                    "de validación."
                ),
            )

        supplier.price_review_status = "validated"
        supplier.price_review_reason = None

        if supplier.price_review_validated_at is None:
            supplier.price_review_validated_at = (
                datetime.now(UTC).isoformat()
            )

    else:
        if supplier.price_review_status != "validated":
            raise HTTPException(
                status_code=409,
                detail="El precio del proveedor no está validado.",
            )

        # Retiramos la decisión manual. El ranking vuelve a
        # evaluar si la evidencia todavía justifica revisión.
        supplier.price_review_status = "not_required"
        supplier.price_review_reason = None
        supplier.price_review_validated_at = None

    ranking = rank_suppliers(result.suppliers)

    result.recommendation_summary = (
        build_recommendation_summary(
            result,
            ranking,
        )
    )
    result.pending_questions = (
        build_pending_questions(
            result,
            ranking,
        )
    )

    updated_body = {
        **body,
        "result": result.model_dump(),
        "ranking": [
            row.model_dump()
            for row in ranking
        ],
    }

    if not update_research(
        research_id,
        updated_body,
    ):
        raise HTTPException(
            status_code=404,
            detail="Investigación no encontrada.",
        )

    return {
        "research_id": research_id,
        **updated_body,
    }


@app.get("/api/history")
def history():
    return list_research()


@app.get("/api/history/{research_id}")
def history_item(research_id: int):
    item = get_research(research_id)
    if not item:
        raise HTTPException(status_code=404, detail="Investigación no encontrada.")
    return item
