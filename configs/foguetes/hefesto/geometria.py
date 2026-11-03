# configs/foguetes/hefesto/geometria.py
"""Geometria medida / nominal do Hefesto (`modo='medido'`) e acessórios de acoplamento."""
from __future__ import annotations

from configs.foguetes.hefesto.aletas_cfg import ALETAS_TRAPEZIO_EQUIV
from src.paths import ARRASTO
from src.specs import GeometriaMedidaSpec

MOTOR_POSITION = 2.78

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

RAIL_BUTTONS = {
    "upper_button_position": 1.39,
    "lower_button_position": 2.30,
    "angular_position": 45.0,
    "radius": 0.02,
}

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
