# configs/foguetes/hefesto/geometria.py
"""Geometria nominal do Hefesto (nominal = sem incertezas)."""
from src.paths import ARRASTO


MOTOR_POSITION = 2.78

FOGUETE = {
    "radius": 0.079,
    "mass": 21.644,
    "coordinate_system_orientation": "nose_to_tail",
    "inertia": (11.784, 11.784, 0.099),
    "center_of_mass_without_motor": 1.35,
    "power_off_drag": str(ARRASTO / "power_off.csv"),
    "power_on_drag":  str(ARRASTO / "power_on.csv"),
}

ALETAS = {
    "n": 4,
    "position": 2.57,
    "shape_points": [(0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)],
}

COIFA = {"length": 0.45, "position": 0, "kind": "lvhaack"}

RAIL_BUTTONS = {
    "upper_button_position": 1.39,
    "lower_button_position": 2.30,
    "angular_position": 45.0,
    "radius": 0.02,
}