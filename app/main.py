from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import RateLimitError
from pydantic import BaseModel

from .db import get_research, init_db, list_research, save_research
from .recommendation import build_recommendation_summary
from .research import research_purchase
from .scoring import rank_suppliers

BASE_DIR = Path(__file__).resolve().parent


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
        body = {
            "result": result.model_dump(),
            "ranking": [r.model_dump() for r in ranking],
            "source_count": len(global_sources),
            "global_sources": global_sources,
            "raw_report": raw_report,
        }
        research_id = save_research(query, body)
        return {"research_id": research_id, **body}
    except RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after")
        headers = (
            {"Retry-After": retry_after}
            if retry_after
            else None
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "El proveedor de IA alcanzó temporalmente "
                "su límite de uso."
            ),
            headers=headers,
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/history")
def history():
    return list_research()


@app.get("/api/history/{research_id}")
def history_item(research_id: int):
    item = get_research(research_id)
    if not item:
        raise HTTPException(status_code=404, detail="Investigación no encontrada.")
    return item
