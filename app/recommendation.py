from __future__ import annotations

from .eligibility import (
    is_supplier_eligible,
    supplier_ineligibility_reason,
)
from .models import RankedSupplier, ResearchResult


def _needs_evidence_reinforcement(supplier) -> bool:
    return (
        supplier.confidence == "baja"
        or not supplier.sources
    )


def _confirmed_price_without_source(supplier) -> bool:
    return (
        supplier.price_status == "confirmado"
        and bool(supplier.price_text)
        and supplier.price_text != "Por confirmar"
        and not supplier.price_sources
    )


def _confirmed_delivery_without_source(supplier) -> bool:
    return (
        supplier.delivery_status == "confirmado"
        and bool(supplier.delivery_time)
        and supplier.delivery_time != "Por confirmar"
        and not supplier.delivery_sources
    )


def _confirmed_credit_without_source(supplier) -> bool:
    return (
        supplier.credit_status == "confirmado"
        and bool(supplier.credit_terms)
        and supplier.credit_terms != "Por confirmar"
        and not supplier.credit_sources
    )


def _confirmed_certifications_without_source(supplier) -> bool:
    return (
        supplier.certifications_status == "confirmado"
        and bool(supplier.certifications)
        and not supplier.certifications_sources
    )


def _available_without_source(supplier) -> bool:
    return (
        supplier.availability_status == "disponible"
        and bool(supplier.availability_text)
        and supplier.availability_text != "Por confirmar"
        and not supplier.availability_sources
    )


def _confirmed_capacity_without_source(supplier) -> bool:
    return (
        supplier.fulfillment_status == "suficiente"
        and supplier.capacity_status == "confirmado"
        and bool(supplier.capacity)
        and supplier.capacity != "Por confirmar"
        and not supplier.capacity_sources
    )


def _ineligibility_explanation(supplier) -> str | None:
    reason = supplier_ineligibility_reason(supplier)

    if reason == "sin_stock":
        return (
            f"{supplier.supplier_name} queda fuera de la recomendación "
            "porque la evidencia reporta que no tiene stock disponible."
        )

    if reason == "capacidad_insuficiente":
        return (
            f"{supplier.supplier_name} queda fuera de la recomendación "
            "porque la capacidad reportada no cubre la cantidad solicitada."
        )

    if reason == "tipo_no_elegible":
        return (
            f"{supplier.supplier_name} queda fuera de la recomendación "
            "porque corresponde a un marketplace o directorio "
            "y no a un proveedor directo elegible."
        )

    return None


def build_recommendation_summary(
    result: ResearchResult,
    ranking: list[RankedSupplier],
) -> str:
    confirmed_matches = [
        row
        for row in ranking
        if (
            row.supplier.product_match_status == "confirmado"
            and is_supplier_eligible(row.supplier)
        )
    ]
    unconfirmed_matches = [
        row
        for row in ranking
        if (
            row.supplier.product_match_status != "confirmado"
            and is_supplier_eligible(row.supplier)
        )
    ]
    ineligible_suppliers = [
        row
        for row in ranking
        if not is_supplier_eligible(row.supplier)
    ]

    if not confirmed_matches:
        if unconfirmed_matches:
            parts = [
                "No hay proveedores con coincidencia exacta del producto "
                "confirmada por la evidencia disponible."
            ]
        else:
            parts = [
                "No hay proveedores elegibles para recomendar "
                "con la evidencia disponible."
            ]

        for row in unconfirmed_matches:
            parts.append(
                f"{row.supplier.supplier_name} queda fuera de la "
                "recomendación porque la coincidencia exacta del "
                "producto no está confirmada."
            )

        for row in ineligible_suppliers:
            explanation = _ineligibility_explanation(row.supplier)
            if explanation:
                parts.append(explanation)

        parts.append(
            "Se requiere ampliar la investigación antes de adjudicar."
        )

        return " ".join(parts)

    top = confirmed_matches[0]
    supplier = top.supplier

    parts = [
        (
            f"{supplier.supplier_name} encabeza el ranking entre los "
            "proveedores con coincidencia de producto confirmada, "
            f"con {top.score:.1f} puntos."
        )
    ]

    for row in unconfirmed_matches:
        parts.append(
            f"{row.supplier.supplier_name} queda fuera de la "
            "recomendación porque la coincidencia exacta del "
            "producto no está confirmada."
        )

    for row in ineligible_suppliers:
        explanation = _ineligibility_explanation(row.supplier)
        if explanation:
            parts.append(explanation)

    if _needs_evidence_reinforcement(supplier):
        if not supplier.sources:
            parts.append(
                f"La evidencia disponible para "
                f"{supplier.supplier_name} no cuenta con fuentes "
                "registradas; antes de adjudicar se debe reforzar "
                "la evidencia."
            )
        else:
            parts.append(
                f"La evidencia disponible para "
                f"{supplier.supplier_name} tiene confianza baja; "
                "antes de adjudicar se debe reforzar la evidencia."
            )

    if (
        supplier.price_status != "por_confirmar"
        and supplier.price_text
        and supplier.price_text != "Por confirmar"
    ):
        parts.append(
            f"Precio reportado: {supplier.price_text}."
        )

    if _confirmed_price_without_source(supplier):
        parts.append(
            f"el precio reportado por "
            f"{supplier.supplier_name} no tiene "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia del precio."
        )

    if (
        supplier.delivery_status != "por_confirmar"
        and supplier.delivery_time
        and supplier.delivery_time != "Por confirmar"
    ):
        parts.append(
            f"Entrega reportada: {supplier.delivery_time}."
        )

    if _confirmed_delivery_without_source(supplier):
        parts.append(
            f"la entrega reportada por "
            f"{supplier.supplier_name} no tiene "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia del tiempo de entrega."
        )

    if _confirmed_credit_without_source(supplier):
        parts.append(
            f"el crédito reportado por "
            f"{supplier.supplier_name} no tiene "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia de las condiciones "
            "de crédito."
        )

    if _confirmed_certifications_without_source(supplier):
        parts.append(
            f"las certificaciones reportadas por "
            f"{supplier.supplier_name} no tienen "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia de las certificaciones."
        )

    if _available_without_source(supplier):
        parts.append(
            f"la disponibilidad reportada por "
            f"{supplier.supplier_name} no tiene "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia de disponibilidad."
        )

    if _confirmed_capacity_without_source(supplier):
        parts.append(
            f"la capacidad reportada por "
            f"{supplier.supplier_name} no tiene "
            "una fuente registrada; antes de adjudicar "
            "se debe confirmar la evidencia de capacidad."
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

    prices_requiring_review = [
        row.supplier
        for row in confirmed_matches
        if row.supplier.price_review_status == "requires_review"
    ]

    for reviewed_supplier in prices_requiring_review:
        price = reviewed_supplier.price_text

        if not price or price == "Por confirmar":
            price_detail = ""
        else:
            price_detail = f" ({price})"

        parts.append(
            f"El precio reportado por "
            f"{reviewed_supplier.supplier_name}"
            f"{price_detail} requiere validación y no se usa "
            "como referencia automática de precio."
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
        if (
            row.supplier.product_match_status == "confirmado"
            and is_supplier_eligible(row.supplier)
        )
    ]
    unconfirmed_matches = [
        row
        for row in ranking
        if (
            row.supplier.product_match_status != "confirmado"
            and is_supplier_eligible(row.supplier)
        )
    ]
    ineligible_suppliers = [
        row
        for row in ranking
        if not is_supplier_eligible(row.supplier)
    ]

    for row in unconfirmed_matches:
        pending.append(
            "Confirmar coincidencia exacta del producto con "
            f"{row.supplier.supplier_name}."
        )

    if not confirmed_matches:
        if ineligible_suppliers and not unconfirmed_matches:
            pending.append(
                "Ampliar la investigación para identificar al menos "
                "un proveedor elegible que cumpla exactamente la "
                "especificación solicitada."
            )
        else:
            pending.append(
                "Ampliar la investigación para confirmar al menos "
                "un proveedor que cumpla exactamente la "
                "especificación solicitada."
            )

        return pending

    for row in confirmed_matches:
        reviewed_supplier = row.supplier

        if reviewed_supplier.price_review_status == "requires_review":
            pending.append(
                "Validar el precio reportado por "
                f"{reviewed_supplier.supplier_name} "
                "antes de usarlo como referencia de precio."
            )

    supplier = confirmed_matches[0].supplier
    name = supplier.supplier_name

    if _needs_evidence_reinforcement(supplier):
        pending.append(
            f"Reforzar la evidencia de {name} antes de adjudicar."
        )

    if _confirmed_price_without_source(supplier):
        pending.append(
            f"Confirmar evidencia del precio reportado por {name}."
        )

    if _confirmed_delivery_without_source(supplier):
        pending.append(
            "Confirmar evidencia del tiempo de entrega reportado por "
            f"{name}."
        )

    if _confirmed_credit_without_source(supplier):
        pending.append(
            "Confirmar evidencia de las condiciones de crédito "
            f"reportadas por {name}."
        )

    if _confirmed_certifications_without_source(supplier):
        pending.append(
            "Confirmar evidencia de las certificaciones reportadas por "
            f"{name}."
        )

    if _available_without_source(supplier):
        pending.append(
            "Confirmar evidencia de la disponibilidad reportada por "
            f"{name}."
        )

    if _confirmed_capacity_without_source(supplier):
        pending.append(
            "Confirmar evidencia de la capacidad reportada por "
            f"{name}."
        )

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
