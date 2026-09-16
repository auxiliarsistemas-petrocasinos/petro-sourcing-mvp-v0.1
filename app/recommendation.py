from __future__ import annotations

from .models import RankedSupplier, ResearchResult


def build_recommendation_summary(
    result: ResearchResult,
    ranking: list[RankedSupplier],
) -> str:
    confirmed_matches = [
        row
        for row in ranking
        if row.supplier.product_match_status == "confirmado"
    ]

    if not confirmed_matches:
        return (
            "No hay proveedores con coincidencia exacta del producto "
            "confirmada por la evidencia disponible. "
            "Se requiere ampliar la investigación antes de adjudicar."
        )

    top = confirmed_matches[0]
    supplier = top.supplier

    parts = [
        (
            f"{supplier.supplier_name} encabeza el ranking entre los "
            "proveedores con coincidencia de producto confirmada, "
            f"con {top.score:.1f} puntos."
        )
    ]

    if (
        supplier.price_status != "por_confirmar"
        and supplier.price_text
        and supplier.price_text != "Por confirmar"
    ):
        parts.append(
            f"Precio reportado: {supplier.price_text}."
        )

    if (
        supplier.delivery_status != "por_confirmar"
        and supplier.delivery_time
        and supplier.delivery_time != "Por confirmar"
    ):
        parts.append(
            f"Entrega reportada: {supplier.delivery_time}."
        )

    alternatives = confirmed_matches[1:3]
    if alternatives:
        names = ", ".join(
            row.supplier.supplier_name
            for row in alternatives
        )
        parts.append(
            "Otras alternativas con coincidencia confirmada: "
            f"{names}."
        )

    pending: list[str] = []

    pending.append(
        f"disponibilidad para {result.quantity}"
    )

    if supplier.credit_status == "por_confirmar":
        pending.append("condiciones de crédito")

    if supplier.estimated_total_delivered_cop is None:
        pending.append(
            f"costo total puesto en {result.destination}"
        )

    if pending:
        if len(pending) == 1:
            pending_text = pending[0]
        else:
            pending_text = (
                ", ".join(pending[:-1])
                + " y "
                + pending[-1]
            )

        parts.append(
            f"Antes de adjudicar, confirmar {pending_text}."
        )

    return " ".join(parts)


def build_pending_questions(
    result: ResearchResult,
    ranking: list[RankedSupplier],
) -> list[str]:
    pending: list[str] = []

    quantity_known = (
        bool(result.quantity)
        and result.quantity.strip().lower() != "por confirmar"
    )
    destination_known = (
        bool(result.destination)
        and result.destination.strip().lower() != "por confirmar"
    )

    if not quantity_known:
        pending.append(
            "¿Qué cantidad necesitas comprar?"
        )

    if not destination_known:
        pending.append(
            "¿Cuál es el destino de entrega?"
        )

    confirmed_matches = [
        row
        for row in ranking
        if row.supplier.product_match_status == "confirmado"
    ]

    if not confirmed_matches:
        pending.append(
            "Ampliar la investigación para confirmar al menos "
            "un proveedor que cumpla exactamente la "
            "especificación solicitada."
        )
        return pending

    supplier = confirmed_matches[0].supplier
    name = supplier.supplier_name

    if quantity_known:
        pending.append(
            f"Confirmar con {name} disponibilidad "
            f"para {result.quantity}."
        )
    else:
        pending.append(
            f"Confirmar disponibilidad del producto con {name}."
        )

    if supplier.price_status != "confirmado":
        pending.append(
            f"Confirmar precio vigente con {name}."
        )

    if supplier.credit_status != "confirmado":
        pending.append(
            f"Confirmar condiciones de crédito con {name}."
        )

    if supplier.delivery_status != "confirmado":
        if destination_known:
            pending.append(
                f"Confirmar tiempo de entrega hasta "
                f"{result.destination} con {name}."
            )
        else:
            pending.append(
                f"Confirmar tiempo de entrega con {name}."
            )

    if supplier.certifications_status != "confirmado":
        pending.append(
            "Confirmar certificaciones o documentos de calidad "
            f"con {name}."
        )

    if supplier.estimated_total_delivered_cop is None:
        if destination_known:
            pending.append(
                f"Confirmar costo total puesto en "
                f"{result.destination} con {name}, "
                "incluyendo flete."
            )
        else:
            pending.append(
                f"Confirmar costo total entregado con {name}, "
                "incluyendo flete."
            )

    return pending
