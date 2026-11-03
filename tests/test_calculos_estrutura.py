"""Testes dos cálculos estruturais (componentes, coifa, aletas, segurança e `resolver()`)."""
from __future__ import annotations

import pytest

from configs import ALETA_IREC, COIFA_IREC, COMPONENTES, HEFESTO, LIMITES_IREC
from src.calculos.aletas import calcular_aleta
from src.calculos.aletas_rasaero import aleta_para_rasaero
from src.calculos.coifa import calcular_coifa
from src.calculos.componentes import derivar_todos
from src.calculos.seguranca import check_kn, check_mass_flux, check_p0, fs_carcaca
from src.agregador_estrutural import resolver


def test_componentes_hefesto() -> None:
    derivados = derivar_todos(COMPONENTES)
    assert len(derivados) == 24
    massa_total = sum(d.massa for d in derivados)
    assert 16.0 < massa_total < 21.0


def test_coifa_hefesto() -> None:
    d = calcular_coifa(COIFA_IREC, raio_base=HEFESTO.raio)
    assert 1.0 < d.massa < 1.6
    assert 0.10 < d.cg < 0.25
    assert d.I_xx_local > 0
    assert d.I_yy_local > 0


def test_aletas_e_rasaero() -> None:
    d = calcular_aleta(ALETA_IREC, r_rocket=HEFESTO.raio)
    assert 3.0 < d.massa_total < 4.0
    assert 0.02 < d.area_planform < 0.03
    assert 2.2 < d.X_cg_absoluto < 2.5

    ras_le = aleta_para_rasaero(ALETA_IREC, span_modo="le")
    ras_te = aleta_para_rasaero(ALETA_IREC, span_modo="te")
    assert ras_le.fin_count == 4
    assert ras_le.span_in > ras_te.span_in


def test_seguranca_medusa_referencia() -> None:
    d_fs = fs_carcaca(2.9122e6, 0.05395, 0.003175, limites=LIMITES_IREC)
    assert pytest.approx(d_fs.valor, abs=0.01) == 2.93
    assert d_fs.ok

    assert check_p0(2.9122e6, limites=LIMITES_IREC).ok
    assert check_kn(232.7390, limites=LIMITES_IREC).ok
    assert check_mass_flux(1249.4661, limites=LIMITES_IREC).ok


def test_seguranca_fail_closed() -> None:
    """Verifica que entradas inválidas ou nulas retornam ok=False e valor=nan."""
    import math

    assert not fs_carcaca(0.0, 0.05, 0.003).ok
    assert not fs_carcaca(-1e6, 0.05, 0.003).ok
    assert not fs_carcaca(1e6, 0.0, 0.003).ok
    assert not fs_carcaca(1e6, 0.05, 0.0).ok
    assert not fs_carcaca(float("nan"), 0.05, 0.003).ok
    assert math.isnan(fs_carcaca(float("nan"), 0.05, 0.003).valor)

    assert not check_p0(None).ok
    assert not check_kn(None).ok
    assert not check_mass_flux(None).ok
    assert not check_p0(float("nan")).ok


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

    d_rkt = r.dict_rocket("off.csv", "on.csv")
    I_11, I_22, I_33 = d_rkt["inertia"]
    # No RocketPy, e_3 (I_33) é o eixo longitudinal de simetria (roll), muito menor que pitch/yaw
    assert I_11 == pytest.approx(r.inercia_transversal)
    assert I_22 == pytest.approx(r.inercia_transversal)
    assert I_33 == pytest.approx(r.inercia_longitudinal)
    assert I_11 > I_33
