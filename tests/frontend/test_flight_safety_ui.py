"""UI component tests for the Flight Safety Envelope panel."""

from __future__ import annotations

from frontend.components.flight_safety_panel import build_flight_safety_rows
from hefesto.domain import (
    FlightSafetyCheck,
    FlightSafetyLimits,
    FlightSafetyReport,
    FlightSafetyStatus,
)


def test_build_flight_safety_rows_maps_traffic_light_badges_and_values() -> None:
    report = FlightSafetyReport(
        limits=FlightSafetyLimits(),
        overall_status=FlightSafetyStatus.FAIL,
        checks=(
            FlightSafetyCheck(
                key="fin_flutter",
                category="Aerodinâmica & Aeroelasticidade",
                name="Fin Flutter (NACA TN 4197)",
                status=FlightSafetyStatus.PASS,
                value=1.85,
                unit="x",
                reference_limit="≥ 1.50",
            ),
            FlightSafetyCheck(
                key="static_margin",
                category="Estabilidade & Weathercocking",
                name="Margem Estática",
                status=FlightSafetyStatus.WARN,
                value=3.8,
                unit="cal",
                reference_limit="1.5 – 3.5 cal",
                recommendation="Risco de superestabilidade.",
            ),
            FlightSafetyCheck(
                key="twr",
                category="Decolagem",
                name="TWR",
                status=FlightSafetyStatus.FAIL,
                value=3.2,
                unit=":1",
                reference_limit="≥ 5.0",
            ),
            FlightSafetyCheck(
                key="parachute_opening_shock",
                category="Recuperação",
                name="Opening Shock",
                status=FlightSafetyStatus.NOT_EVALUATED,
                value=None,
                unit="G",
                reference_limit="≤ 15 G",
            ),
        ),
    )

    rows = build_flight_safety_rows(report)
    assert [r.status_label for r in rows] == [
        "APROVADO",
        "ATENÇÃO",
        "REPROVADO",
        "NÃO AVALIADO",
    ]
    assert [r.badge_color for r in rows] == ["positive", "warning", "negative", "grey"]
    assert rows[0].formatted_value == "1.85x"
    assert rows[1].formatted_value == "3.80 cal"
    assert rows[2].formatted_value == "3.20:1"
    assert rows[3].formatted_value == "N/D"
