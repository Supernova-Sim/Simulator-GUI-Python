"""End-to-end ork_parity gate: analytical drag vs OpenRocket apogee/Mach targets."""

from __future__ import annotations

from hefesto.domain import DragSource
from hefesto.physics import derive_dry_mass
from hefesto.services import (
    compose_simulation_config,
    load_rocket_spec,
    run_deterministic,
)

# OpenRocket 26.11 flight of hefesto_1.41.ork (ISA, launch rail 84 deg, 6.48 m).
ORK_REFERENCE_APOGEE_AGL_M = 3393.406064
ORK_REFERENCE_MAX_MACH = 0.961311
APOGEE_TOLERANCE = 0.045
MAX_MACH_TOLERANCE = 0.010


def test_hefesto_1_4_parity_mission_uses_analytical_drag() -> None:
    preset = load_rocket_spec("hefesto_1.4")
    assert preset.drag_source == "analytical"
    assert preset.power_off_drag.asset_name is None
    assert preset.power_on_drag.asset_name is None
    assert derive_dry_mass(preset) == 15.769610321481428


def test_ork_parity_mission_matches_openrocket_reference() -> None:
    config = compose_simulation_config(mission_id="ork_parity")
    result = run_deterministic(config)

    flight = result.flight
    apogee_delta = flight.apogee_agl_m / ORK_REFERENCE_APOGEE_AGL_M - 1.0
    mach_delta = flight.max_mach / ORK_REFERENCE_MAX_MACH - 1.0

    assert abs(apogee_delta) <= APOGEE_TOLERANCE, (
        f"apogee {flight.apogee_agl_m:.3f} m vs OpenRocket {ORK_REFERENCE_APOGEE_AGL_M:.3f} m "
        f"({100 * apogee_delta:+.2f}%)"
    )
    assert abs(mach_delta) <= MAX_MACH_TOLERANCE, (
        f"max Mach {flight.max_mach:.4f} vs OpenRocket {ORK_REFERENCE_MAX_MACH:.4f} "
        f"({100 * mach_delta:+.2f}%)"
    )
    assert flight.total_impulse_ns > 11500.0


def test_golden_master_rocket_stays_on_legacy_csv_drag() -> None:
    """hefesto_v1 must keep the CSV-backed curves the Golden Master baseline was built from."""
    golden = load_rocket_spec("hefesto_v1")
    legacy: DragSource = "legacy_csv"
    assert golden.drag_source == legacy
    assert golden.power_off_drag.asset_name == "power_off.csv"
    assert golden.power_on_drag.asset_name == "power_on.csv"
    assert derive_dry_mass(golden) == 18.85049031412732
