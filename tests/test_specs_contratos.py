"""Testes de contratos de domínio (validação fail-fast em `src.specs`) e arquitetura."""
from __future__ import annotations

import ast

import pytest

from src.paths import RAIZ
from src.specs import (
    AletaSpec,
    CoifaSpec,
    FogueteSpec,
    GeometriaMedidaSpec,
    GrainSpec,
    LimitesSeguranca,
    MassaPontualSpec,
    MotorSpec,
    TuboSpec,
)


def test_arquitetura_src_nao_importa_configs() -> None:
    """Garante que nenhum arquivo dentro de `src/` importa `configs`."""
    src_dir = RAIZ / "src"
    violacoes: list[str] = []

    for py_file in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "configs" or alias.name.startswith("configs."):
                        violacoes.append(f"{py_file.relative_to(RAIZ)}:{node.lineno} -> import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "configs" or mod.startswith("configs."):
                    violacoes.append(f"{py_file.relative_to(RAIZ)}:{node.lineno} -> from {mod} import ...")

    assert not violacoes, "Violação de camada (src/ importando configs/):\n" + "\n".join(violacoes)


def test_grain_spec_validacao() -> None:
    with pytest.raises(ValueError, match="length deve ser > 0"):
        GrainSpec(length=0.0, outer_radius=0.05, inner_radius=0.02)

    with pytest.raises(ValueError, match="inner_radius"):
        GrainSpec(length=0.15, outer_radius=0.05, inner_radius=0.05)


def test_tubo_spec_validacao() -> None:
    t = TuboSpec("Tubo", raio_externo=0.08, espessura=0.002, comprimento=0.5, posicao=1.0, densidade=1850)
    assert pytest.approx(t.raio_interno) == 0.078

    with pytest.raises(ValueError, match="espessura"):
        TuboSpec("Tubo inválido", raio_externo=0.05, espessura=0.06, comprimento=0.5, posicao=1.0, densidade=1850)


def test_massa_pontual_coifa_aleta_validacao() -> None:
    with pytest.raises(ValueError, match="massa deve ser > 0"):
        MassaPontualSpec("Item", massa=-1.0, posicao=0.5, raio_equivalente=0.05, comprimento=0.1)

    with pytest.raises(ValueError, match="kind inválido"):
        CoifaSpec("Coifa", length=0.45, kind="parabolica", position=0.0, thickness=0.003, densidade=1900)

    with pytest.raises(ValueError, match="n deve ser >= 1"):
        AletaSpec(
            "Aleta", n=0, root_chord=0.2, tip_chord=0.1,
            span_le=0.15, span_te=0.15, sweep_length=0.05,
            thickness=0.005, position=2.0, densidade=2700,
        )


def test_motor_spec_validacao() -> None:
    # Sem ric_path nem thrust_curve_path deve falhar imediatamente
    with pytest.raises(ValueError, match="ric_path"):
        MotorSpec(nome="Inválido", case_inner_radius=0.05, case_wall_thickness=0.003)

    # Sem ric_path (só .eng), exige grains, propellant_density e raios da tubeira
    with pytest.raises(ValueError, match="grains"):
        MotorSpec(
            nome="Só .eng incompleto",
            case_inner_radius=0.05,
            case_wall_thickness=0.003,
            thrust_curve_path="qualquer.eng",
        )


def test_limites_e_foguete_spec_validacao() -> None:
    with pytest.raises(ValueError, match="fs_min_carcaca"):
        LimitesSeguranca(fs_min_carcaca=0.0)

    motor = MotorSpec(
        nome="M", case_inner_radius=0.05, case_wall_thickness=0.003, ric_path="dummy.ric"
    )
    with pytest.raises(ValueError, match="modo 'calculado'"):
        FogueteSpec(
            nome="Vazio",
            raio=0.079,
            motor=motor,
            motor_position=2.78,
            power_off_drag="off.csv",
            power_on_drag="on.csv",
            rail_buttons={},
            reefed={},
            unreefed={},
        )

    gm = GeometriaMedidaSpec(
        raio=0.079,
        massa_seca=21.644,
        inercia_transversal=11.784,
        inercia_longitudinal=0.099,
        cg_sem_motor=1.35,
        coifa_length=0.45,
        coifa_kind="lvhaack",
        coifa_position=0.0,
        aletas_n=4,
        aletas_position=2.57,
        aletas_shape_points=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
    )
    assert gm.inercia_rocketpy == (11.784, 11.784, 0.099)
