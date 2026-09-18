from app.eligibility import is_supplier_eligible
from app.models import SupplierResearch


def supplier_with_type(
    supplier_type: str,
) -> SupplierResearch:
    return SupplierResearch(
        supplier_name="Proveedor prueba",
        supplier_type=supplier_type,
        product_match="Producto solicitado",
        product_match_status="confirmado",
        evidence_summary="Evidencia de prueba.",
    )


def test_marketplace_is_not_eligible():
    assert not is_supplier_eligible(
        supplier_with_type("Marketplace")
    )


def test_directory_is_not_eligible_case_insensitive():
    assert not is_supplier_eligible(
        supplier_with_type("DIRECTORIO DE PROVEEDORES")
    )


def test_multiple_sellers_with_accent_is_not_eligible():
    assert not is_supplier_eligible(
        supplier_with_type(
            "Directorio de múltiples vendedores"
        )
    )


def test_direct_supplier_is_eligible():
    assert is_supplier_eligible(
        supplier_with_type(
            "Distribuidor mayorista"
        )
    )


def test_unknown_supplier_type_remains_eligible():
    assert is_supplier_eligible(
        supplier_with_type("Por confirmar")
    )


def test_ineligibility_reason_reports_out_of_stock():
    from app.eligibility import supplier_ineligibility_reason

    item = supplier_with_type("Distribuidor mayorista")
    item.availability_status = "sin_stock"

    assert supplier_ineligibility_reason(item) == "sin_stock"


def test_ineligibility_reason_reports_insufficient_capacity():
    from app.eligibility import supplier_ineligibility_reason

    item = supplier_with_type("Distribuidor mayorista")
    item.fulfillment_status = "insuficiente"

    assert (
        supplier_ineligibility_reason(item)
        == "capacidad_insuficiente"
    )


def test_ineligibility_reason_reports_non_direct_supplier():
    from app.eligibility import supplier_ineligibility_reason

    item = supplier_with_type(
        "Directorio de múltiples vendedores"
    )

    assert (
        supplier_ineligibility_reason(item)
        == "tipo_no_elegible"
    )
