from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from openai import OpenAI
from tavily import TavilyClient

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


@dataclass(frozen=True)
class SearchConfig:
    provider: str
    api_key: str | None


class InvalidPurchaseRequestError(ValueError):
    pass


def _validate_purchase_intent(
    intent: PurchaseRequestInterpretation,
) -> None:
    product = (intent.product or "").strip()

    invalid_products = {
        "",
        "por confirmar",
        "n/a",
        "ninguno",
        "none",
    }

    if (
        not intent.is_purchase_request
        or product.lower() in invalid_products
    ):
        raise InvalidPurchaseRequestError(
            "Este agente solo atiende solicitudes de "
            "abastecimiento. Indica qué producto o "
            "servicio necesitas comprar, cotizar "
            "o comparar."
        )




def _load_search_config() -> SearchConfig:
    provider = os.getenv("SEARCH_PROVIDER", "native").strip().lower()

    if provider == "native":
        return SearchConfig(
            provider="native",
            api_key=None,
        )

    if provider == "tavily":
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta TAVILY_API_KEY para usar SEARCH_PROVIDER=tavily."
            )

        return SearchConfig(
            provider="tavily",
            api_key=api_key,
        )

    raise RuntimeError(
        f"SEARCH_PROVIDER no soportado: {provider}. "
        "Usa 'native' o 'tavily'."
    )


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

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta GEMINI_API_KEY para usar AI_PROVIDER=gemini."
            )

        return AIConfig(
            provider="gemini",
            api_key=api_key,
            base_url=None,
            interpret_model=os.getenv(
                "GEMINI_INTERPRET_MODEL",
                "gemini-3.6-flash",
            ),
            research_model=os.getenv(
                "GEMINI_RESEARCH_MODEL",
                "gemini-3.6-flash",
            ),
            extract_model=os.getenv(
                "GEMINI_EXTRACT_MODEL",
                "gemini-3.6-flash",
            ),
            search_tool={},
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
        "Usa 'openai', 'groq' o 'gemini'."
    )


PURCHASE_INTERPRETATION_PROMPT = """
Interpreta una solicitud de compra sin inventar información.

Reglas:
- Decide primero si el mensaje pertenece al dominio de abastecimiento/compras.
- `is_purchase_request` debe ser true cuando el usuario quiera comprar, abastecer,
  cotizar, buscar proveedores, comparar proveedores, validar disponibilidad,
  condiciones comerciales o evaluar un producto/servicio con intención de compra.
- `is_purchase_request` debe ser false para preguntas de historia, cultura general,
  política, clima, programación, recetas, conversación casual o conocimiento general
  sin una necesidad de abastecimiento.
- Una pregunta meramente informativa sobre un producto, por ejemplo
  "¿qué es un guante de nitrilo?", no es por sí sola una solicitud de compra.
- Si `is_purchase_request` es false, no inventes una necesidad de compra para
  convertir la pregunta en una consulta de proveedores.
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
   Identifica también la presentación exacta a la que corresponde el precio:
   unidad, caja, paquete, par, kg, litro, metro u otra base. Cuando una presentación
   contenga múltiples unidades, conserva explícitamente esa cantidad, por ejemplo
   "caja x100 unidades".
8. Si no hay precio público, escribe 'Por confirmar'; no fabriques un valor.
   No asumas moneda, presentación ni cantidad contenida cuando la fuente sea ambigua.
9. Para disponibilidad, solo afirma "disponible" o "sin stock" cuando la fuente
   lo indique explícitamente. Que exista una ficha de producto no demuestra existencia.
   No afirmes que hay cantidad suficiente para cubrir la compra salvo que la fuente
   sustente explícitamente esa cantidad.
10. Para crédito, evalúa únicamente crédito comercial otorgado directamente por el proveedor.
   Solo afirma días/plazo cuando exista evidencia explícita de pago diferido al proveedor,
   por ejemplo 30, 45 o 60 días contra factura. Tarjetas de crédito, cuotas de pasarelas,
   marketplaces o financiación de terceros como MercadoPago, Addi, Sistecrédito u otros
   NO cuentan como crédito comercial del proveedor. Puedes mencionarlos como forma de pago,
   pero no como días de crédito del proveedor.
11. Para entrega, si se infiere por distancia o cobertura, márcala como estimada.
12. Para certificaciones/estándares, incluye solo los que tengan evidencia.
13. Incluye datos de contacto públicos cuando estén disponibles.
14. Cita las fuentes usadas. La recomendación final debe ser útil para un comprador.
15. Considera que el criterio de decisión es: precio, crédito, tiempo de entrega,
    certificaciones/estándares y calidad de evidencia.
16. No confundas un portal que lista productos con el proveedor real.
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
- Para precios, conserva la presentación original y normaliza únicamente cuando
  la evidencia sea explícita.
- `price_amount_cop` es el valor numérico en COP correspondiente exactamente a
  `price_basis`. Ejemplo: "$15.000 COP caja x100" -> 15000.
- `price_basis` describe aquello que compra ese valor: por ejemplo "caja",
  "paquete", "unidad", "par", "kg", "litro" o "metro".
- `price_basis_quantity` es la cantidad de `price_base_unit` contenida en esa
  presentación. Ejemplo: caja x100 unidades -> 100. Si no está explícita, null.
- `price_base_unit` es la unidad canónica que permite comparar presentaciones.
  Usa términos simples y consistentes como "unidad", "par", "kg", "litro" o
  "metro". Para una caja x100 guantes, usa "unidad".
- Si `price_basis` y `price_base_unit` son la misma medida y el precio es directo
  por esa medida, `price_basis_quantity` puede ser null.
- `price_cop_per_unit` es el precio normalizado en COP por `price_base_unit`
  únicamente cuando pueda calcularse de forma inequívoca. Ejemplo:
  15000 COP por caja x100 unidades -> 150 COP por unidad. Si no, null.
- No conviertas monedas extranjeras a COP ni interpretes un símbolo "$" ambiguo
  como COP salvo que la fuente permita identificar razonablemente la moneda.
- No inventes contenido de empaque. Si una fuente dice solo "$15.000 por caja"
  sin indicar cuántas unidades contiene, no inventes `price_basis_quantity`.
- `credit_days` solo si aparece explícitamente un plazo de crédito comercial otorgado
  directamente por el proveedor; si no, null.
- Tarjetas de crédito, cuotas, pasarelas de pago, marketplaces y financiación de terceros
  como MercadoPago, Addi, Sistecrédito, PayU o similares NO son crédito comercial del
  proveedor y nunca deben convertirse en `credit_days`.
- Si existe una forma de pago financiada por un tercero, puede conservarse descriptivamente
  en `credit_terms`, pero `credit_days` debe ser null salvo que exista además evidencia
  independiente de crédito comercial directo del proveedor.
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


GEMINI_TRANSIENT_ERROR_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}


def _gemini_model_candidates(
    primary_model: str,
) -> list[str]:
    configured = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "",
    )

    candidates: list[str] = []

    for model in [
        primary_model,
        *configured.split(","),
    ]:
        model = model.strip()

        if model and model not in candidates:
            candidates.append(model)

    return candidates


def _run_with_gemini_fallback(
    operation: Any,
    primary_model: str,
) -> Any:
    last_error: genai_errors.APIError | None = None

    for model in _gemini_model_candidates(
        primary_model
    ):
        try:
            return operation(model)
        except genai_errors.APIError as exc:
            if exc.code not in GEMINI_TRANSIENT_ERROR_CODES:
                raise

            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "No hay modelos Gemini configurados."
    )


def _interpret_purchase_request_gemini(
    client: Any,
    query: str,
    model: str,
) -> PurchaseRequestInterpretation:
    response = client.models.generate_content(
        model=model,
        contents=(
            f"{PURCHASE_INTERPRETATION_PROMPT}\n\n"
            "SOLICITUD DEL USUARIO:\n"
            f"{query}"
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PurchaseRequestInterpretation,
        ),
    )

    intent = response.parsed

    if intent is None:
        raise RuntimeError(
            "Gemini no pudo interpretar la solicitud de compra."
        )

    if not isinstance(intent, PurchaseRequestInterpretation):
        intent = PurchaseRequestInterpretation.model_validate(intent)

    return intent


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


def _research_with_gemini_from_evidence(
    client: Any,
    research_brief: str,
    evidence: str,
    model: str,
) -> str:
    response = client.models.generate_content(
        model=model,
        contents=(
            f"{SYSTEM_RESEARCH_PROMPT}\n\n"
            "REGLA CRÍTICA ADICIONAL:\n"
            "Usa exclusivamente la evidencia web proporcionada abajo. "
            "No afirmes que navegaste otras páginas y no inventes fuentes. "
            "Cuando un dato no aparezca en la evidencia, indica "
            "'Por confirmar'.\n\n"
            f"{research_brief}\n\n"
            "EVIDENCIA WEB RECUPERADA:\n"
            f"{evidence}"
        ),
    )

    report = (response.text or "").strip()

    if not report:
        raise RuntimeError(
            "Gemini no produjo un informe de investigación."
        )

    return report


def _extract_research_result_gemini(
    client: Any,
    report: str,
    sources: list[dict[str, str]],
    model: str,
) -> ResearchResult:
    sources_text = "\n".join(
        f"- {source['title']}: {source['url']}"
        for source in sources
    )

    response = client.models.generate_content(
        model=model,
        contents=(
            f"{EXTRACTION_PROMPT}\n\n"
            "INFORME DE INVESTIGACIÓN:\n"
            f"{report}\n\n"
            "FUENTES DISPONIBLES:\n"
            f"{sources_text}"
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResearchResult,
        ),
    )

    result = response.parsed

    if result is None:
        raise RuntimeError(
            "Gemini no pudo estructurar el resultado de investigación."
        )

    if not isinstance(result, ResearchResult):
        result = ResearchResult.model_validate(result)

    return result


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


def _search_with_tavily(
    query: str,
    api_key: str,
    max_results: int = 8,
) -> tuple[list[dict[str, str]], str]:
    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        topic="general",
        country="colombia",
    )

    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    evidence_blocks: list[str] = []

    for result in response.get("results", []):
        url = (result.get("url") or "").strip()

        if not url or url in seen:
            continue

        seen.add(url)

        title = (result.get("title") or url).strip()
        content = (result.get("content") or "").strip()

        sources.append(
            {
                "title": title,
                "url": url,
            }
        )

        evidence_blocks.append(
            "\n".join(
                [
                    f"FUENTE {len(sources)}",
                    f"Título: {title}",
                    f"URL: {url}",
                    f"Contenido: {content or 'Sin contenido disponible.'}",
                ]
            )
        )

    if not sources:
        raise RuntimeError(
            "Tavily no devolvió resultados web utilizables."
        )

    return sources, "\n\n".join(evidence_blocks)


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

        supplier.availability_sources = valid_supplier_sources(
            supplier.availability_sources,
            supplier_urls,
        )
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

            supplier.availability_sources = []
            supplier.price_sources = []
            supplier.credit_sources = []
            supplier.delivery_sources = []
            supplier.certifications_sources = []
            supplier.capacity_sources = []
            supplier.contact_sources = []

            supplier.availability_text = "Por confirmar"
            supplier.availability_status = "por_confirmar"
            supplier.fulfillment_status = "por_confirmar"

            supplier.price_text = "Por confirmar"
            supplier.price_amount_cop = None
            supplier.price_basis = "Por confirmar"
            supplier.price_basis_quantity = None
            supplier.price_base_unit = "Por confirmar"
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

        if not supplier.availability_sources:
            supplier.availability_text = "Por confirmar"
            supplier.availability_status = "por_confirmar"
            supplier.fulfillment_status = "por_confirmar"

        if not supplier.price_sources:
            supplier.price_text = "Por confirmar"
            supplier.price_amount_cop = None
            supplier.price_basis = "Por confirmar"
            supplier.price_basis_quantity = None
            supplier.price_base_unit = "Por confirmar"
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
    search_config = _load_search_config()

    if config.provider == "gemini":
        if search_config.provider != "tavily":
            raise RuntimeError(
                "AI_PROVIDER=gemini requiere "
                "SEARCH_PROVIDER=tavily."
            )

        if not search_config.api_key:
            raise RuntimeError(
                "Falta TAVILY_API_KEY para investigar con Gemini."
            )

        client = genai.Client(
            api_key=config.api_key,
        )

        intent = _run_with_gemini_fallback(
            lambda model: _interpret_purchase_request_gemini(
                client,
                query,
                model,
            ),
            config.interpret_model,
        )

        _validate_purchase_intent(intent)
        research_brief = _build_research_brief(intent)

        search_query = (
            "proveedor distribuidor mayorista "
            f"{intent.product} "
            f"{' '.join(intent.required_specifications)} "
            "Colombia "
            f"{intent.destination or ''}"
        ).strip()

        sources, evidence = _search_with_tavily(
            query=search_query,
            api_key=search_config.api_key,
            max_results=8,
        )

        report = _run_with_gemini_fallback(
            lambda model: _research_with_gemini_from_evidence(
                client=client,
                research_brief=research_brief,
                evidence=evidence,
                model=model,
            ),
            config.research_model,
        )

        result = _run_with_gemini_fallback(
            lambda model: _extract_research_result_gemini(
                client=client,
                report=report,
                sources=sources,
                model=model,
            ),
            config.extract_model,
        )

        result = _apply_purchase_interpretation(
            result,
            intent,
        )
        result = _enforce_source_evidence(
            result,
            sources,
        )

        return result, sources, report

    if search_config.provider != "native":
        raise RuntimeError(
            "SEARCH_PROVIDER=tavily actualmente "
            "requiere AI_PROVIDER=gemini."
        )

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
    _validate_purchase_intent(intent)
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
