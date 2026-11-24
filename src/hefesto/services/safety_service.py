"""Flight safety envelope evaluation service over completed SimulationResult snapshots."""

from __future__ import annotations

from hefesto.domain import (
    FlightSafetyLimits,
    FlightSafetyReport,
    SimulationResult,
)
from hefesto.physics import evaluate_flight_safety


def evaluate_simulation_flight_safety(
    result: SimulationResult,
    limits: FlightSafetyLimits | None = None,
) -> FlightSafetyReport:
    """Evaluate the Flight Safety Envelope from a SimulationResult (supports legacy snapshots)."""
    executed = result.executed_config
    rocket = executed.mission.rocket if executed is not None else None
    motor = rocket.motor if rocket is not None else None
    return evaluate_flight_safety(
        result.flight,
        rocket=rocket,
        motor=motor,
        motor_safety=result.safety,
        limits=limits,
    )


__all__ = ["evaluate_simulation_flight_safety"]
