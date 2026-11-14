"""Testes do subsistema de motor (`src.motor`: derivador, adaptador OpenMotor, segurança) e análise Polars."""
from __future__ import annotations

import math

import polars as pl
import pytest

from configs import ENG_MEDUSA, LIMITES_IREC, MOTOR_IREC, VARIACOES, criar_variacao
from src.especificacoes import GrainSpec, MotorSpec
from src.motor.derivador import derivar_motor
from src.motor.seguranca import check_kn, check_mass_flux, check_p0, fs_carcaca
from src.simulacao.construtor_foguete import build_motor


# ── Derivação & Adaptador OpenMotor (src/motor/derivador.py, adaptador_openmotor.py) ──
def test_derivar_motor_oficial_ric() -> None:
    d = derivar_motor(MOTOR_IREC)
    assert d.fonte == "ric"
    assert len(d.grains) == 6
    assert d.total_impulse > 10000.0
    assert d.p0_pico is not None and d.p0_pico > 0
    assert d.kn_pico is not None and d.kn_pico > 0
    assert d.curva_empuxo is not None and len(d.curva_empuxo) > 20

    # Convenção RocketPy: (I_transversal, I_transversal, I_longitudinal)
    I_11, I_22, I_33 = d.dry_inertia
    assert I_11 == pytest.approx(I_22)
    assert I_11 > I_33


def test_overrides_atualizam_tanto_balistica_quanto_geometria_dos_graos() -> None:
    """Garante que `overrides` em `coreDiameter` e `throat` atualizam os grãos e tubeira em `MotorDerivado`."""
    d_base = derivar_motor(MOTOR_IREC)

    # 1. Override na garganta (−6%)
    spec_throat = VARIACOES["throat_estreito"]
    d_throat = derivar_motor(spec_throat)
    assert d_throat.throat_radius == pytest.approx(d_base.throat_radius * 0.94)
    assert d_throat.p0_pico > d_base.p0_pico
    assert d_throat.kn_pico > d_base.kn_pico

    # 2. Override no coreDiameter de todos os grãos (45 mm → raio interno 22.5 mm)
    spec_core = criar_variacao(
        {"grains.*.properties.coreDiameter": 0.045},
        nome="Teste Core 45mm",
    )
    d_core = derivar_motor(spec_core)
    for g in d_core.grains:
        assert g.inner_radius == pytest.approx(0.0225)
    assert d_core.grain_inner_radius_effective == pytest.approx(0.0225)
    assert d_core.propellant_mass != pytest.approx(d_base.propellant_mass)


def test_whitelist_bloqueia_parametro_proibido() -> None:
    with pytest.raises(ValueError, match="fora da whitelist"):
        criar_variacao({"propellant.density": 1900.0})


def test_fallback_eng_sem_ric() -> None:
    spec_eng = MotorSpec(
        nome="Medusa via .eng",
        case_inner_radius=0.05395,
        case_wall_thickness=0.003175,
        thrust_curve_path=ENG_MEDUSA,
        grains=(GrainSpec(length=0.16, outer_radius=0.049345, inner_radius=0.0205),) * 7,
        propellant_density=1841.0,
        nozzle_exit_radius=0.039,
        throat_radius=0.017,
        nozzle_position=0.016,
    )
    d = derivar_motor(spec_eng)
    assert d.fonte == "eng"
    assert d.total_impulse > 10000.0
    assert d.p0_pico is None
    assert d.diagnosticos == ()


def test_grao_medio_heterogeneo_conservacao_massa() -> None:
    """Verifica que grãos heterogêneos usam o grão médio equivalente e conservam massa no RocketPy."""
    graos = (
        GrainSpec(length=0.10, outer_radius=0.049, inner_radius=0.020),
        GrainSpec(length=0.15, outer_radius=0.049, inner_radius=0.022),
        GrainSpec(length=0.20, outer_radius=0.049, inner_radius=0.018),
    )
    spec = MotorSpec(
        nome="MotorHeterogeneo",
        case_inner_radius=0.05,
        case_wall_thickness=0.003,
        thrust_curve_path=ENG_MEDUSA,
        grains=graos,
        propellant_density=1841.0,
        nozzle_exit_radius=0.039,
        throat_radius=0.017,
    )
    motor_rkt, d = build_motor(spec)

    assert d.grain_height_effective == pytest.approx((0.10 + 0.15 + 0.20) / 3.0)
    assert d.grain_outer_radius_effective == pytest.approx(0.049)
    assert d.curva_empuxo is not None

    massa_rkt = motor_rkt.propellant_mass(0)
    assert math.isclose(massa_rkt, d.propellant_mass, rel_tol=1e-5)
    assert math.isfinite(motor_rkt.total_impulse)


# ── Segurança Estrutural e Balística (src/motor/seguranca.py) ─────────────────
def test_seguranca_medusa_referencia() -> None:
    d_fs = fs_carcaca(2.9122e6, 0.05395, 0.003175, limites=LIMITES_IREC)
    assert pytest.approx(d_fs.valor, abs=0.01) == 2.93
    assert d_fs.ok

    assert check_p0(2.9122e6, limites=LIMITES_IREC).ok
    assert check_kn(232.7390, limites=LIMITES_IREC).ok
    assert check_mass_flux(1249.4661, limites=LIMITES_IREC).ok


def test_seguranca_fail_closed() -> None:
    """Verifica que entradas inválidas ou nulas retornam ok=False e valor=nan."""
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


# ── CLI & Pós-Processamento Polars (scripts/analisar_motor.py, centralControle/rodar.py) ──
def test_resolver_motor_cli() -> None:
    """Verifica a resolução de presets de motor pela CLI `centralControle.rodar`."""
    from centralControle.rodar import _resolver_motor

    assert _resolver_motor(None) is None
    assert _resolver_motor("oficial") is None
    assert _resolver_motor("throat_estreito") is VARIACOES["throat_estreito"]
    assert _resolver_motor(MOTOR_IREC) is MOTOR_IREC

    with pytest.raises(ValueError, match="não existe"):
        _resolver_motor("inexistente")


def test_analisar_motor_polars() -> None:
    """Verifica filtragem, ranking e ponto ótimo sobre DataFrame Polars em `analisar_motor`."""
    from scripts.analisar_motor import (
        achar_otimo,
        filtrar,
        params_do_registro,
        rankear,
    )

    df = pl.DataFrame(
        [
            {
                "nozzle.throat": 0.032,
                "success": True,
                "impulse_Ns": 13200.0,
                "p0_MPa": 4.2,
                "kn": 260.0,
                "mass_flux": 1300.0,
                "fs_carcaca": 2.1,
                "ok_geral": False,
                "erro": "",
            },
            {
                "nozzle.throat": 0.034,
                "success": True,
                "impulse_Ns": 12800.0,
                "p0_MPa": 3.5,
                "kn": 230.0,
                "mass_flux": 1200.0,
                "fs_carcaca": 2.9,
                "ok_geral": True,
                "erro": "",
            },
            {
                "nozzle.throat": 0.036,
                "success": True,
                "impulse_Ns": 12400.0,
                "p0_MPa": 2.9,
                "kn": 205.0,
                "mass_flux": 1100.0,
                "fs_carcaca": 3.4,
                "ok_geral": True,
                "erro": "",
            },
        ]
    )

    assert params_do_registro(df) == ["nozzle.throat"]

    viaveis = filtrar(df, fs_min=2.5)
    assert viaveis.height == 2
    ordenado = rankear(viaveis, "impulse_Ns")
    assert ordenado["impulse_Ns"].to_list() == [12800.0, 12400.0]

    otimo = achar_otimo(df, "impulse_Ns", fs_min=2.5)
    assert otimo is not None
    assert otimo["nozzle.throat"] == pytest.approx(0.034)
    assert otimo["impulse_Ns"] == pytest.approx(12800.0)
