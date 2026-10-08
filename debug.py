import importlib, sys
for mod in list(sys.modules):
    if mod.startswith(("src", "configs", "scripts")):
        del sys.modules[mod]

from configs import (
    MOTOR_IREC, ALETA_IREC, COIFA_IREC, IREC,
    MotorSpec, AletaSpec, CoifaSpec,
    FOGUETE, COMPONENTES, ALETAS_TRAPEZIO_EQUIV,
    REEFED, UNREEFED, RAIL_BUTTONS,
)
print("✓ configs facade importa")

from src.calculos.motor import derivar_motor
from src.ambiente import build_irec
from src.modelos import build_rocket
from rocketpy import Flight

d = derivar_motor(MOTOR_IREC)
print(f"Motor: fonte={d.fonte}, impulse={d.total_impulse:.1f} N·s, FS={d.diagnosticos[0].valor:.3f}")

foguete = build_rocket(tipo_aletas="freeform", spec_aleta=ALETA_IREC)
voo = Flight(rocket=foguete.rocket, environment=build_irec(), **IREC)
apogee_agl = voo.apogee - 1401
print(f"Apogeu AGL: {apogee_agl:.1f} m")