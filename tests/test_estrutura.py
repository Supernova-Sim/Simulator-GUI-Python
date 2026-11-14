"""Testes dos cálculos estruturais (`src.estrutura`: componentes, coifa, aletas e agregador)."""
from __future__ import annotations

import pytest

from configs import ALETA_IREC, COIFA_IREC, COMPONENTES, HEFESTO
from src.estrutura.agregador import resolver
from src.estrutura.aletas import aleta_para_rasaero, calcular_aleta
from src.estrutura.coifa import calcular_coifa
from src.estrutura.componentes import derivar_todos


# ── Componentes (src/estrutura/componentes.py) ────────────────────────────────
def test_componentes_hefesto() -> None:
    derivados = derivar_todos(COMPONENTES)
    assert len(derivados) == 24
    massa_total = sum(d.massa for d in derivados)
    assert 16.0 < massa_total < 21.0


# ── Coifa (src/estrutura/coifa.py) ────────────────────────────────────────────
def test_coifa_hefesto() -> None:
    d = calcular_coifa(COIFA_IREC, raio_base=HEFESTO.raio)
    assert 1.0 < d.massa < 1.6
    assert 0.10 < d.cg < 0.25
    assert d.I_xx_local > 0
    assert d.I_yy_local > 0


# ── Aletas & RASAero (src/estrutura/aletas.py) ────────────────────────────────
def test_aletas_e_rasaero() -> None:
    d = calcular_aleta(ALETA_IREC, r_rocket=HEFESTO.raio)
    assert 3.0 < d.massa_total < 4.0
    assert 0.02 < d.area_planform < 0.03
    assert 2.2 < d.X_cg_absoluto < 2.5

    ras_le = aleta_para_rasaero(ALETA_IREC, span_modo="le")
    ras_te = aleta_para_rasaero(ALETA_IREC, span_modo="te")
    assert ras_le.fin_count == 4
    assert ras_le.span_in > ras_te.span_in


# ── Agregador & Steiner (src/estrutura/agregador.py) ──────────────────────────
def test_resolver_convencao_inercia_rocketpy() -> None:
    """Verifica que `resolver()` entrega `(I_t, I_t, I_l)` conforme convenção do RocketPy."""
    r = resolver(
        componentes=COMPONENTES,
        spec_aleta=ALETA_IREC,
        spec_coifa=COIFA_IREC,
        raio=HEFESTO.raio,
    )
    assert 21.0 < r.massa_seca < 26.0
    assert 1.2 < r.cg_sem_motor < 1.8
    assert r.inercia_transversal > r.inercia_longitudinal

    I_11, I_22, I_33 = r.inercia_rocketpy
    # No RocketPy, e_3 (I_33) é o eixo longitudinal de simetria (roll), muito menor que pitch/yaw
    assert I_11 == pytest.approx(r.inercia_transversal)
    assert I_22 == pytest.approx(r.inercia_transversal)
    assert I_33 == pytest.approx(r.inercia_longitudinal)
    assert I_11 > I_33
