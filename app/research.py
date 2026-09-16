from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .models import PurchaseRequestInterpretation, ResearchResult


@dataclass(frozen=True)
class AIConfig:
    provider: str
    api_key: str
    base_url: str | None
    interpret_model: str
    research_model: str
    extract_model: str
    search_tool: dict[str, Any]


def _load_ai_config() -> AIConfig:
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta GROQ_API_KEY para usar AI_PROVIDER=groq."
            )

        return AIConfig(
            provider="groq",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            interpret_model=os.getenv(
                "GROQ_INTERPRET_MODEL",
                "openai/gpt-oss-20b",
            ),
            research_model=os.getenv(
                "GROQ_RESEARCH_MODEL",
                "openai/gpt-oss-20b",
            ),
            extract_model=os.getenv(
                "GROQ_EXTRACT_MODEL",
                "openai/gpt-oss-20b",
            ),
            search_tool={
                "type": "browser_search",
            },
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta OPENAI_API_KEY para usar AI_PROVIDER=openai."
            )

        extract_model = os.getenv(
            "OPENAI_EXTRACT_MODEL",
            "gpt-5.6-luna",
        )

        return AIConfig(
            provider="openai",
            api_key=api_key,
            base_url=None,
            interpret_model=os.getenv(
                "OPENAI_INTERPRET_MODEL",
                extract_model,
            ),
            research_model=os.getenv(
                "OPENAI_RESEARCH_MODEL",
                "gpt-5.6-terra",
            ),
            extract_model=extract_model,
            search_tool={
                "type": "web_search",
                "search_context_size": "high",
            },
        )

    raise RuntimeError(
        f"AI_PROVIDER no soportado: {provider}. "
        "Usa 'openai' o 'groq'."
    )


PURCHASE_INTERPRETATION_PROMPT = """
Interpreta una solicitud de compra sin inventar información.

Reglas:
- Extrae únicamente información explícita o inequívoca del mensaje del usuario.
- Identifica el producto principal solicitado.
- Conserva cantidad y unidad tal como se entienden de la solicitud.
- Identifica el destino de entrega solo si está indicado.
- Extrae especificaciones obligatorias como talla, material, marca, referencia,
  presentación, dimensiones, norma, grado, empaque u otras características.
- Si cantidad o destino no están presentes, usa null.
- No completes datos faltantes por conocimiento general o suposición.
- `interpreted_request` debe ser una reformulación fiel y breve de la solicitud.
"""


SYSTEM_RESEARCH_PROMPT = """
Eres un analista senior de abastecimiento para una empresa en Colombia.
Tu objetivo es investigar proveedores REALES y actuales para una necesidad de compra.

Reglas obligatorias:
1. Busca fabricantes, productores, distribuidores, mayoristas y comercializadores pertinentes.
2. No inventes proveedores, teléfonos, correos, precios, certificaciones, crédito, capacidad ni plazos.
3. Distingue explícitamente cada dato como CONFIRMADO, ESTIMADO o POR CONFIRMAR.
4. Prioriza fuentes primarias (sitio oficial, catálogo oficial, cámara/asociación, ficha del proveedor).
5. Puedes usar directorios/marketplaces como evidencia secundaria, pero indícalo.
6. Busca idealmente entre 5 y 10 proveedores si el mercado lo permite.
7. Para precio, distingue precio del producto de flete/costo puesto en destino.
8. Si no hay precio público, escribe 'Por confirmar'; no fabriques un valor.
9. Para crédito, solo afirma días/plazo si hay evidencia explícita. De lo contrario: 'Por confirmar'.
10. Para entrega, si se infiere por distancia o cobertura, márcala como estimada.
11. Para certificaciones/estándares, incluye solo los que tengan evidencia.
12. Incluye datos de contacto públicos cuando estén disponibles.
13. Cita las fuentes usadas. La recomendación final debe ser útil para un comprador.
14. Considera que el criterio de decisión es: precio, crédito, tiempo de entrega,
    certificaciones/estándares y calidad de evidencia.
15. No confundas un portal que lista productos con el proveedor real.
"""


EXTRACTION_PROMPT = """
Convierte el informe de investigación en la estructura solicitada.

Reglas:
- Conserva únicamente proveedores reales presentes en el informe.
- `price_status`, `credit_status`, `delivery_status`, `certifications_status`,
  `capacity_status` y `product_match_status` solo pueden ser:
  "confirmado", "estimado" o "por_confirmar".
- `confidence` solo puede ser "alta", "media" o "baja".
- `estimated_total_delivered_cop` solo debe tener un número si el informe ofrece
  un total puesto en destino o una estimación razonablemente sustentada. Si no, null.
- `price_cop_per_unit` solo si el precio puede expresarse razonablemente en COP por
  la unidad relevante; si no, null.
- `credit_days` solo si aparece explícitamente; si no, null.
- `delivery_days` puede ser numérico si está confirmado o estimado de forma clara; si no, null.
- No inventes URLs. Usa exclusivamente las URL entregadas en la sección FUENTES DISPONIBLES.
- `sources` contiene las fuentes que sustentan la existencia, identidad o pertinencia general del proveedor.
- `price_sources` contiene únicamente fuentes que sustentan directamente el precio.
- `credit_sources` contiene únicamente fuentes que sustentan directamente el plazo o condiciones de crédito.
- `delivery_sources` contiene únicamente fuentes que sustentan directamente el plazo de entrega.
- `certifications_sources` contiene únicamente fuentes que sustentan directamente las certificaciones indicadas.
- `capacity_sources` contiene únicamente fuentes que sustentan directamente la capacidad declarada del proveedor.
- `contact_sources` contiene únicamente fuentes oficiales o confiables que sustentan teléfono, correo o sitio web del proveedor.
- Todas esas fuentes deben provenir exclusivamente de FUENTES DISPONIBLES.
- Toda URL incluida en `price_sources`, `credit_sources`, `delivery_sources`, `certifications_sources`, `capacity_sources` o `contact_sources` también debe estar incluida en `sources` del mismo proveedor.
- Nunca uses una fuente asociada a otro proveedor para respaldar datos de este proveedor.
- Una fuente general del proveedor NO demuestra por sí sola precio, crédito, entrega ni certificaciones.
- No agregues una URL a una lista de evidencia específica si esa fuente no sustenta realmente ese dato.
- Mantén "Por confirmar" cuando falte información o evidencia específica.
"""


def _interpret_purchase_request(
    client: Any,
    query: str,
    model: str,
) -> PurchaseRequestInterpretation:
    parsed = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": PURCHASE_INTERPRETATION_PROMPT,
            },
            {
                "role": "user",
                "content": query,
            },
        ],
        text_format=PurchaseRequestInterpretation,
    )

    intent = parsed.output_parsed
    if intent is None:
        raise RuntimeError(
            "El modelo no pudo interpretar la solicitud de compra."
        )

    return intent


def _build_research_brief(
    intent: PurchaseRequestInterpretation,
) -> str:
    quantity = intent.quantity or "POR CONFIRMAR"
    destination = intent.destination or "POR CONFIRMAR"

    if intent.required_specifications:
        specifications = "\n".join(
            f"- {specification}"
            for specification in intent.required_specifications
        )
    else:
        specifications = "- POR CONFIRMAR"

    return (
        "SOLICITUD DE COMPRA INTERPRETADA\n"
        f"Producto: {intent.product}\n"
        f"Cantidad: {quantity}\n"
        f"Destino: {destination}\n"
        "Especificaciones requeridas:\n"
        f"{specifications}\n"
        f"Interpretación: {intent.interpreted_request}"
    )


def _apply_purchase_interpretation(
    result: ResearchResult,
    intent: PurchaseRequestInterpretation,
) -> ResearchResult:
    normalized = result.model_copy(deep=True)

    normalized.interpreted_request = intent.interpreted_request
    normalized.product = intent.product
    normalized.quantity = intent.quantity or "Por confirmar"
    normalized.destination = intent.destination or "Por confirmar"
    normalized.required_specifications = list(
        intent.required_specifications
    )

    pending_questions = list(normalized.pending_questions)

    if not intent.quantity:
        question = "¿Qué cantidad necesitas comprar?"
        if question not in pending_questions:
            pending_questions.append(question)

    if not intent.destination:
        question = "¿Cuál es el destino de entrega?"
        if question not in pending_questions:
            pending_questions.append(question)

    normalized.pending_questions = pending_questions

    return normalized


def _collect_url_annotations(response: Any) -> list[dict[str, str]]:
    seen = set()
    sources = []

    def add_source(url: str | None, title: str | None = None) -> None:
        if not url or url in seen:
            return

        seen.add(url)
        sources.append(
            {
                "title": title or url,
                "url": url,
            }
        )

    for output in getattr(response, "output", []) or []:
        output_type = getattr(output, "type", None)

        if output_type == "message":
            for content in getattr(output, "content", []) or []:
                for ann in getattr(content, "annotations", []) or []:
                    if getattr(ann, "type", None) != "url_citation":
                        continue

                    add_source(
                        getattr(ann, "url", None),
                        getattr(ann, "title", None),
                    )

            continue

        if (
            output_type == "mcp_call"
            and getattr(output, "name", None) == "browser.open"
        ):
            browser_output = getattr(output, "output", None)

            if not isinstance(browser_output, str):
                continue

            url = None
            title = None

            for line in browser_output.splitlines():
                if line.startswith("L1: URL: "):
                    url = line.removeprefix("L1: URL: ").strip()
                elif line.startswith("L2: "):
                    title = line.removeprefix("L2: ").strip()

            add_source(url, title)

    return sources



def _enforce_source_evidence(
    result: ResearchResult,
    global_sources: list[dict[str, str]],
) -> ResearchResult:
    allowed_urls = {
        source["url"]
        for source in global_sources
        if source.get("url")
    }

    validated = result.model_copy(deep=True)

    def valid_global_sources(field_sources):
        return [
            source
            for source in field_sources
            if source.url in allowed_urls
        ]

    for supplier in validated.suppliers:
        supplier.sources = valid_global_sources(supplier.sources)

        supplier_urls = {
            source.url
            for source in supplier.sources
        }

        def valid_supplier_sources(field_sources, supplier_urls):
            return [
                source
                for source in field_sources
                if source.url in allowed_urls
                and source.url in supplier_urls
            ]

        supplier.price_sources = valid_supplier_sources(
            supplier.price_sources,
            supplier_urls,
        )
        supplier.credit_sources = valid_supplier_sources(
            supplier.credit_sources,
            supplier_urls,
        )
        supplier.delivery_sources = valid_supplier_sources(
            supplier.delivery_sources,
            supplier_urls,
        )
        supplier.certifications_sources = valid_supplier_sources(
            supplier.certifications_sources,
            supplier_urls,
        )
        supplier.capacity_sources = valid_supplier_sources(
            supplier.capacity_sources,
            supplier_urls,
        )
        supplier.contact_sources = valid_supplier_sources(
            supplier.contact_sources,
            supplier_urls,
        )

        if not supplier.sources:
            supplier.confidence = "baja"
            supplier.product_match_status = "por_confirmar"

            supplier.price_sources = []
            supplier.credit_sources = []
            supplier.delivery_sources = []
            supplier.certifications_sources = []
            supplier.capacity_sources = []
            supplier.contact_sources = []

            supplier.price_text = "Por confirmar"
            supplier.price_cop_per_unit = None
            supplier.estimated_total_delivered_cop = None
            supplier.price_status = "por_confirmar"

            supplier.credit_terms = "Por confirmar"
            supplier.credit_days = None
            supplier.credit_status = "por_confirmar"

            supplier.delivery_time = "Por confirmar"
            supplier.delivery_days = None
            supplier.delivery_status = "por_confirmar"

            supplier.certifications = []
            supplier.certifications_status = "por_confirmar"

            supplier.capacity = "Por confirmar"
            supplier.capacity_status = "por_confirmar"

            supplier.phone = "Por confirmar"
            supplier.email = "Por confirmar"
            supplier.website = "Por confirmar"

            continue

        if not supplier.price_sources:
            supplier.price_text = "Por confirmar"
            supplier.price_cop_per_unit = None
            supplier.estimated_total_delivered_cop = None
            supplier.price_status = "por_confirmar"

        if not supplier.credit_sources:
            supplier.credit_terms = "Por confirmar"
            supplier.credit_days = None
            supplier.credit_status = "por_confirmar"

        if not supplier.delivery_sources:
            supplier.delivery_time = "Por confirmar"
            supplier.delivery_days = None
            supplier.delivery_status = "por_confirmar"

        if not supplier.certifications_sources:
            supplier.certifications = []
            supplier.certifications_status = "por_confirmar"

        if not supplier.capacity_sources:
            supplier.capacity = "Por confirmar"
            supplier.capacity_status = "por_confirmar"

        if not supplier.contact_sources:
            supplier.phone = "Por confirmar"
            supplier.email = "Por confirmar"
            supplier.website = "Por confirmar"

    return validated


def research_purchase(query: str) -> tuple[ResearchResult, list[dict[str, str]], str]:
    config = _load_ai_config()

    client_kwargs: dict[str, Any] = {
        "api_key": config.api_key,
    }
    if config.base_url:
        client_kwargs["base_url"] = config.base_url

    client = OpenAI(**client_kwargs)

    intent = _interpret_purchase_request(
        client,
        query,
        config.interpret_model,
    )
    research_brief = _build_research_brief(intent)

    research_request: dict[str, Any] = {
        "model": config.research_model,
        "tools": [config.search_tool],
        "input": [
            {"role": "system", "content": SYSTEM_RESEARCH_PROMPT},
            {
                "role": "user",
                "content": (
                    "Investiga esta necesidad de compra y produce un informe detallado, "
                    "comparativo y sustentado:\n\n" + research_brief
                ),
            },
        ],
    }

    if config.provider == "openai":
        research_request["reasoning"] = {"effort": "medium"}

    if config.provider == "groq":
        research_request["tool_choice"] = "required"

    research_response = client.responses.create(**research_request)

    report = research_response.output_text
    sources = _collect_url_annotations(research_response)

    sources_text = (
        "\n".join(f"- {s['title']} | {s['url']}" for s in sources)
        or "- No se recuperaron URL explícitas."
    )

    parse_input = f"""
INFORME DE INVESTIGACIÓN:
{report}

FUENTES DISPONIBLES:
{sources_text}
"""

    parsed = client.responses.parse(
        model=config.extract_model,
        input=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": parse_input},
        ],
        text_format=ResearchResult,
    )

    result = parsed.output_parsed
    if result is None:
        raise RuntimeError("El modelo no devolvió una estructura válida.")

    result = _apply_purchase_interpretation(result, intent)
    result = _enforce_source_evidence(result, sources)

    return result, sources, report
