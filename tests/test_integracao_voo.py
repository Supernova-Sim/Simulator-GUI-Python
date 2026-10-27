"""Testes de integração de montagem e voo (`modo='calculado'` vs `modo='medido'`)."""
from __future__ import annotations

import pytest
from rocketpy import Flight

from configs import HEFESTO, IREC
from src.ambiente import build_irec
from src.modelos import build_rocket
from src.paths import ATMOSFERA, DATA, ENTRADA, MOTORES, OPENMOTOR, RAIZ, SAIDA


def test_paths_canonicos_existem() -> None:
    for p in (RAIZ, DATA, ENTRADA, SAIDA, ATMOSFERA, MOTORES, OPENMOTOR):
        assert p.exists(), f"Caminho canônico ausente: {p}"


def test_build_rocket_modos_calculado_e_medido() -> None:
    f_calc = build_rocket(HEFESTO, modo="calculado", tipo_aletas="freeform")
    f_med = build_rocket(HEFESTO, modo="medido", tipo_aletas="freeform")

    assert f_calc.modo == "calculado"
    assert f_calc.foguete_resolvido is not None
    assert f_med.modo == "medido"
    assert f_med.foguete_resolvido is None

    # Massas secas distintas e explícitas conforme cada modo
    assert f_med.rocket.mass == pytest.approx(HEFESTO.geometria_medida.massa_seca)
    assert f_calc.rocket.mass == pytest.approx(f_calc.foguete_resolvido.massa_seca)
    assert f_calc.rocket.mass != pytest.approx(f_med.rocket.mass)

    # Ambos usam a convenção correta do RocketPy: I_11 == I_22 > I_33
    assert f_calc.rocket.I_11_without_motor == pytest.approx(f_calc.rocket.I_22_without_motor)
    assert f_calc.rocket.I_11_without_motor > f_calc.rocket.I_33_without_motor

    env = build_irec()
    voo = Flight(rocket=f_calc.rocket, environment=env, **IREC)
    apogee_agl = voo.apogee - env.elevation
    assert 2000.0 < apogee_agl < 3200.0
    assert voo.min_stability_margin > 1.0
