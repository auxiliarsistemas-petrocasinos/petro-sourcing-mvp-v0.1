from __future__ import annotations

import os
from typing import Any
from openai import OpenAI

from .models import ResearchResult


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
- Vincula a cada proveedor solo las fuentes que realmente lo sustentan.
- Mantén "Por confirmar" cuando falte información.
"""


def _collect_url_annotations(response: Any) -> list[dict[str, str]]:
    seen = set()
    sources = []

    for output in getattr(response, "output", []) or []:
        if getattr(output, "type", None) != "message":
            continue
        for content in getattr(output, "content", []) or []:
            for ann in getattr(content, "annotations", []) or []:
                if getattr(ann, "type", None) != "url_citation":
                    continue
                url = getattr(ann, "url", None)
                title = getattr(ann, "title", None) or url
                if url and url not in seen:
                    seen.add(url)
                    sources.append({"title": title, "url": url})
    return sources


def research_purchase(query: str) -> tuple[ResearchResult, list[dict[str, str]], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta OPENAI_API_KEY. Copia .env.example a .env y agrega una clave de la API."
        )

    research_model = os.getenv("OPENAI_RESEARCH_MODEL", "gpt-5.6-terra")
    extract_model = os.getenv("OPENAI_EXTRACT_MODEL", "gpt-5.6-luna")

    client = OpenAI(api_key=api_key)

    research_response = client.responses.create(
        model=research_model,
        reasoning={"effort": "medium"},
        tools=[
            {
                "type": "web_search",
                "search_context_size": "high",
            }
        ],
        input=[
            {"role": "system", "content": SYSTEM_RESEARCH_PROMPT},
            {
                "role": "user",
                "content": (
                    "Investiga esta necesidad de compra y produce un informe detallado, "
                    "comparativo y sustentado:\n\n"
                    + query
                ),
            },
        ],
    )

    report = research_response.output_text
    sources = _collect_url_annotations(research_response)

    sources_text = "\n".join(
        f"- {s['title']} | {s['url']}" for s in sources
    ) or "- No se recuperaron URL explícitas."

    parse_input = f"""
INFORME DE INVESTIGACIÓN:
{report}

FUENTES DISPONIBLES:
{sources_text}
"""

    parsed = client.responses.parse(
        model=extract_model,
        input=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": parse_input},
        ],
        text_format=ResearchResult,
    )

    result = parsed.output_parsed
    if result is None:
        raise RuntimeError("El modelo no devolvió una estructura válida.")

    return result, sources, report
