from app.models import SupplierResearch
from app.scoring import rank_suppliers


def supplier(
    name: str,
    *,
    total: float | None = None,
    price_status: str = "por_confirmar",
) -> SupplierResearch:
    return SupplierResearch(
        supplier_name=name,
        product_match="Producto solicitado",
        product_match_status="confirmado",
        estimated_total_delivered_cop=total,
        price_status=price_status,
        evidence_summary="Proveedor usado para pruebas.",
        confidence="media",
    )


def test_cheapest_known_price_gets_highest_price_score():
    cheap = supplier("Proveedor barato", total=100_000, price_status="confirmado")
    expensive = supplier("Proveedor caro", total=125_000, price_status="confirmado")

    ranking = rank_suppliers([expensive, cheap])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Proveedor barato"].price_score == 100.0
    assert rows["Proveedor caro"].price_score == 80.0


def test_missing_price_does_not_receive_artificial_price_points():
    known = supplier("Precio conocido", total=100_000, price_status="confirmado")
    unknown = supplier("Precio desconocido")

    ranking = rank_suppliers([unknown, known])
    rows = {row.supplier.supplier_name: row for row in ranking}

    assert rows["Precio conocido"].price_score == 100.0
    assert rows["Precio desconocido"].price_score == 0.0
    assert rows["Precio conocido"].rank < rows["Precio desconocido"].rank


def test_all_missing_prices_receive_zero_price_score():
    first = supplier("Proveedor A")
    second = supplier("Proveedor B")

    ranking = rank_suppliers([first, second])

    assert all(row.price_score == 0.0 for row in ranking)


def test_ranks_are_consecutive_starting_at_one():
    suppliers = [
        supplier("Proveedor A", total=100_000, price_status="confirmado"),
        supplier("Proveedor B", total=120_000, price_status="confirmado"),
        supplier("Proveedor C"),
    ]

    ranking = rank_suppliers(suppliers)

    assert [row.rank for row in ranking] == [1, 2, 3]
