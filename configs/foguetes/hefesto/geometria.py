# configs/foguetes/hefesto/geometria.py
"""Geometria completa do Hefesto: coifa, aletas, recuperação e medidas de bancada."""
from __future__ import annotations

from configs.limites import ALUMINIO_6061, COIFA_EFETIVA
from src.caminhos import ARRASTO
from src.especificacoes import AletaSpec, CoifaSpec, GeometriaMedidaSpec

# ============================================================
#  Coifa (modo calculado)
# ============================================================
ESPESSURA_COIFA = 0.003   # m — 3 mm

COIFA_IREC = CoifaSpec(
    nome="Coifa Hefesto",
    length=0.45,
    kind="lvhaack",
    position=0.0,
    thickness=ESPESSURA_COIFA,
    densidade=COIFA_EFETIVA,
    massa_extra=1.300 - 0.8724,
    posicao_massa_extra=0.0,
)

# ============================================================
#  Aletas (modo calculado + equivalente trapezoidal)
# ============================================================
ALETA_IREC = AletaSpec(
    nome="IREC 2026 — Solução #1",
    n=4,
    root_chord=0.2267,
    tip_chord=0.0699,
    span_le=0.19179,
    span_te=0.17133,
    sweep_length=0.008,
    thickness=0.0119,
    position=2.2369,
    densidade=ALUMINIO_6061,
)

ALETAS_TRAPEZIO_EQUIV = {
    "n": 4,
    "root_chord": 0.18,
    "tip_chord": 0.07458606,
    "span": 0.13999711,
    "sweep_length": 0.10051811,
    "position": 2.57,
    "cant_angle": 0.0,
}

# ============================================================
#  Recuperação (paraquedas) e acoplamento
# ============================================================
REEFED = {"name": "reefed", "cd_s": 0.85, "radius": 0.6, "trigger": "apogee", "lag": 1}
UNREEFED = {"name": "unreefed", "cd_s": 1.5, "radius": 3.8 / 2, "trigger": 450, "lag": 1}

MOTOR_POSITION = 2.78

RAIL_BUTTONS = {
    "upper_button_position": 1.39,
    "lower_button_position": 2.30,
    "angular_position": 45.0,
    "radius": 0.02,
}

# ============================================================
#  Geometria medida / nominal (bancada / OpenRocket, modo='medido')
# ============================================================
FOGUETE = {
    "radius": 0.079,
    "mass": 21.644,
    "coordinate_system_orientation": "nose_to_tail",
    "inertia": (11.784, 11.784, 0.099),
    "center_of_mass_without_motor": 1.35,
    "power_off_drag": str(ARRASTO / "power_off.csv"),
    "power_on_drag": str(ARRASTO / "power_on.csv"),
}

ALETAS = {
    "n": 4,
    "position": 2.57,
    "shape_points": [
        (0.0, 0.0),
        (0.07, 0.12),
        (0.21, 0.14),
        (0.18, 0.0),
    ],
}

COIFA = {"length": 0.45, "position": 0.0, "kind": "lvhaack"}

GEOMETRIA_MEDIDA_HEFESTO = GeometriaMedidaSpec(
    raio=FOGUETE["radius"],
    massa_seca=FOGUETE["mass"],
    inercia_transversal=FOGUETE["inertia"][0],
    inercia_longitudinal=FOGUETE["inertia"][2],
    cg_sem_motor=FOGUETE["center_of_mass_without_motor"],
    coifa_length=COIFA["length"],
    coifa_kind=COIFA["kind"],
    coifa_position=COIFA["position"],
    aletas_n=ALETAS["n"],
    aletas_position=ALETAS["position"],
    aletas_shape_points=tuple(ALETAS["shape_points"]),
    aletas_cant_angle=0.0,
    aletas_trapezio_equiv=ALETAS_TRAPEZIO_EQUIV,
)
