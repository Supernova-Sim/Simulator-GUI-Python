# src/especificacoes.py
"""Especificações de domínio (Specs), validação fail-fast e whitelist de overrides.

Define todos os contratos de entrada do projeto sem importar `configs/` nem
dependências pesadas (OpenMotor/RocketPy), garantindo pureza no `import`.
Todas as unidades estão no Sistema Internacional (SI: m, kg, s, Pa, kg/m³),
salvo indicação explícita (como ângulos em graus).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PERFIS_COIFA_VALIDOS = ("conical", "lvhaack", "ogive")


# ============================================================
#  Helpers de Validação e Serialização
# ============================================================
def _exigir_positivo(contexto: str, **campos: float) -> None:
    """Falha imediatamente quando qualquer campo numérico é `<= 0`."""
    for nome, valor in campos.items():
        if valor <= 0:
            raise ValueError(f"{contexto}: {nome} deve ser > 0 (recebido: {valor})")


def _serializar_dataclass(obj: Any) -> dict[str, Any]:
    """Serializa uma dataclass convertendo `Path` para `str` e tuplas para listas."""
    def _conv(v: Any) -> Any:
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, (tuple, list)):
            return [_conv(x) for x in v]
        if isinstance(v, dict):
            return {k: _conv(val) for k, val in v.items()}
        return v

    return _conv(dataclasses.asdict(obj))


# ============================================================
#  Validação de Overrides (dot-path + wildcard)
# ============================================================
def _normalizar_path(path: str) -> str:
    """Substitui índices numéricos por '*' para comparação com a whitelist."""
    return ".".join("*" if p.isdigit() else p for p in path.split("."))


def validar_overrides(
    overrides: dict[str, Any],
    whitelist: set[str] | None = None,
) -> None:
    """Verifica se todos os paths de `overrides` pertencem à `whitelist`."""
    if whitelist is None:
        return
    invalidos = [p for p in overrides if _normalizar_path(p) not in whitelist]
    if invalidos:
        linhas = ["Parâmetros fora da whitelist:"] + [f"  ✗ {p}" for p in invalidos]
        linhas += ["", "Whitelist atual:"] + [f"  ✓ {w}" for w in sorted(whitelist)]
        raise ValueError("\n".join(linhas))


# ============================================================
#  Limites de Segurança
# ============================================================
@dataclass(frozen=True)
class LimitesSeguranca:
    """Critérios de aceitação estrutural e operacional (ex.: IREC)."""
    fs_min_carcaca: float = 2.0
    fs_alvo_carcaca: float = 3.0
    fs_min_aletas: float = 2.0
    fs_min_estrutura: float = 2.0
    fs_min_recuperacao: float = 2.0

    p0_max: float = 8.0e6           # Pa
    kn_max: float = 250.0           # —
    mass_flux_max: float = 1406.0   # kg/(m²·s)
    port_throat_min: float = 2.0    # —
    erosion_max_garganta: float = 0.02

    sigma_lim_carcaca: float = 145e6  # Pa — Alumínio 6063-T5

    def __post_init__(self) -> None:
        _exigir_positivo(
            "LimitesSeguranca",
            fs_min_carcaca=self.fs_min_carcaca,
            p0_max=self.p0_max,
            kn_max=self.kn_max,
            mass_flux_max=self.mass_flux_max,
            sigma_lim_carcaca=self.sigma_lim_carcaca,
        )


LIMITES_PADRAO = LimitesSeguranca()


# ============================================================
#  Motor
# ============================================================
@dataclass(frozen=True)
class GrainSpec:
    """Grão propelente cilíndrico oco (BATES)."""
    length: float             # m
    outer_radius: float       # m
    inner_radius: float       # m

    def __post_init__(self) -> None:
        _exigir_positivo("GrainSpec", length=self.length, outer_radius=self.outer_radius)
        if self.inner_radius < 0 or self.inner_radius >= self.outer_radius:
            raise ValueError(
                f"GrainSpec.inner_radius ({self.inner_radius}) deve estar entre 0 e "
                f"outer_radius ({self.outer_radius})"
            )

    def to_dict(self) -> dict[str, float]:
        return _serializar_dataclass(self)


@dataclass(frozen=True)
class MotorSpec:
    """Especificação declarativa de um motor sólido."""
    nome: str

    # ---------- Carcaça ----------
    case_inner_radius: float
    case_wall_thickness: float
    case_density: float = 2700.0

    # ---------- Montagem / Tubeira ----------
    grain_separation: float = 0.010
    nozzle_position: float = 0.0

    # ---------- Fontes de dados (pelo menos uma obrigatória) ----------
    ric_path: str | Path | None = None
    thrust_curve_path: str | Path | None = None

    # ---------- Geometria manual (obrigatória apenas se ric_path for None) ----------
    grains: tuple[GrainSpec, ...] = ()
    propellant_density: float | None = None
    nozzle_exit_radius: float | None = None
    throat_radius: float | None = None

    # ---------- Opcionais da carcaça ----------
    case_length: float | None = None
    margin_nozzle_side: float = 0.075
    margin_forward_side: float = 0.075

    dry_mass: float | None = None
    dry_mass_extra: float = 0.0
    nozzle_mass: float = 0.0

    dry_inertia_override: tuple[float, float, float] | None = None

    # ---------- Overrides de simulação (dot-path sobre o .ric em memória) ----------
    overrides: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.nome or not self.nome.strip():
            raise ValueError("MotorSpec.nome não pode ser vazio.")
        ctx = f"MotorSpec('{self.nome}')"
        _exigir_positivo(
            ctx,
            case_inner_radius=self.case_inner_radius,
            case_wall_thickness=self.case_wall_thickness,
            case_density=self.case_density,
        )
        if self.grain_separation < 0:
            raise ValueError(f"{ctx}: grain_separation deve ser >= 0 (recebido: {self.grain_separation})")
        if self.ric_path is None and self.thrust_curve_path is None:
            raise ValueError(f"{ctx}: defina pelo menos 'ric_path' ou 'thrust_curve_path'.")
        if self.ric_path is None:
            if not self.grains:
                raise ValueError(f"{ctx}: sem 'ric_path', o campo 'grains' é obrigatório.")
            for campo in ("propellant_density", "nozzle_exit_radius", "throat_radius"):
                val = getattr(self, campo)
                if val is None or val <= 0:
                    raise ValueError(f"{ctx}: sem 'ric_path', '{campo}' > 0 é obrigatório.")

    def to_dict(self) -> dict[str, Any]:
        """Dict serializável (JSON-friendly) com os campos da especificação."""
        dados = _serializar_dataclass(self)
        if not dados.get("overrides"):
            dados["overrides"] = None
        return dados


# ============================================================
#  Componentes e Superfícies Aerodinâmicas (Modo Calculado)
# ============================================================
@dataclass(frozen=True)
class TuboSpec:
    """Cilindro oco (ou maciço quando espessura == raio_externo)."""
    nome: str
    raio_externo: float
    espessura: float
    comprimento: float
    posicao: float
    densidade: float
    massa_extra: float = 0.0

    def __post_init__(self) -> None:
        ctx = f"TuboSpec('{self.nome}')"
        _exigir_positivo(
            ctx,
            raio_externo=self.raio_externo,
            comprimento=self.comprimento,
            densidade=self.densidade,
        )
        if self.espessura <= 0 or self.espessura > self.raio_externo:
            raise ValueError(
                f"{ctx}: espessura ({self.espessura}) deve estar entre 0 e raio_externo ({self.raio_externo})"
            )

    @property
    def raio_interno(self) -> float:
        return self.raio_externo - self.espessura


@dataclass(frozen=True)
class MassaPontualSpec:
    """Componente interno com massa fixa e geometria equivalente para inércia."""
    nome: str
    massa: float
    posicao: float
    raio_equivalente: float
    comprimento: float

    def __post_init__(self) -> None:
        ctx = f"MassaPontualSpec('{self.nome}')"
        _exigir_positivo(ctx, massa=self.massa)
        if self.raio_equivalente < 0:
            raise ValueError(f"{ctx}: raio_equivalente deve ser >= 0 (recebido: {self.raio_equivalente})")
        if self.comprimento < 0:
            raise ValueError(f"{ctx}: comprimento deve ser >= 0 (recebido: {self.comprimento})")


@dataclass(frozen=True)
class AletaSpec:
    """Conjunto de aletas trapezoidais/freeform em SI."""
    nome: str
    n: int
    root_chord: float
    tip_chord: float
    span_le: float
    span_te: float
    sweep_length: float
    thickness: float
    position: float
    densidade: float
    cant_angle: float = 0.0

    def __post_init__(self) -> None:
        ctx = f"AletaSpec('{self.nome}')"
        if self.n < 1:
            raise ValueError(f"{ctx}: n deve ser >= 1 (recebido: {self.n})")
        if self.tip_chord < 0:
            raise ValueError(f"{ctx}: tip_chord deve ser >= 0 (recebido: {self.tip_chord})")
        _exigir_positivo(
            ctx,
            root_chord=self.root_chord,
            span_le=self.span_le,
            span_te=self.span_te,
            thickness=self.thickness,
            densidade=self.densidade,
        )

    @property
    def shape_points(self) -> list[tuple[float, float]]:
        """Polígono da aleta no plano (axial, radial) a partir da raiz."""
        return [
            (0.0, 0.0),
            (self.sweep_length, self.span_le),
            (self.sweep_length + self.tip_chord, self.span_te),
            (self.root_chord, 0.0),
        ]


@dataclass(frozen=True)
class CoifaSpec:
    """Coifa modelada como casca fina sobre o perfil `kind`."""
    nome: str
    length: float
    kind: str
    position: float
    thickness: float
    densidade: float
    massa_extra: float = 0.0
    posicao_massa_extra: float | None = None

    def __post_init__(self) -> None:
        ctx = f"CoifaSpec('{self.nome}')"
        _exigir_positivo(ctx, length=self.length, thickness=self.thickness, densidade=self.densidade)
        if self.kind not in PERFIS_COIFA_VALIDOS:
            raise ValueError(f"{ctx}: kind inválido {self.kind!r}. Valores aceitos: {PERFIS_COIFA_VALIDOS}")


# ============================================================
#  Geometria Medida (Modo Medido de Bancada / OpenRocket)
# ============================================================
@dataclass(frozen=True)
class GeometriaMedidaSpec:
    """Propriedades globais medidas diretamente na bancada/OpenRocket (`modo='medido'`)."""
    raio: float
    massa_seca: float
    inercia_transversal: float
    inercia_longitudinal: float
    cg_sem_motor: float
    coifa_length: float
    coifa_kind: str
    coifa_position: float
    aletas_n: int
    aletas_position: float
    aletas_shape_points: tuple[tuple[float, float], ...]
    aletas_cant_angle: float = 0.0
    aletas_trapezio_equiv: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _exigir_positivo(
            "GeometriaMedidaSpec",
            raio=self.raio,
            massa_seca=self.massa_seca,
            inercia_transversal=self.inercia_transversal,
            inercia_longitudinal=self.inercia_longitudinal,
        )
        if self.coifa_kind not in PERFIS_COIFA_VALIDOS:
            raise ValueError(
                f"GeometriaMedidaSpec: coifa_kind inválido {self.coifa_kind!r}. "
                f"Valores aceitos: {PERFIS_COIFA_VALIDOS}"
            )

    @property
    def inercia_rocketpy(self) -> tuple[float, float, float]:
        """Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)."""
        return (self.inercia_transversal, self.inercia_transversal, self.inercia_longitudinal)


# ============================================================
#  Agregado Completo de Foguete
# ============================================================
@dataclass(frozen=True)
class FogueteSpec:
    """Identidade completa de um foguete (suporta modos 'calculado' e 'medido')."""
    nome: str
    raio: float
    motor: MotorSpec
    motor_position: float
    power_off_drag: str | Path
    power_on_drag: str | Path
    rail_buttons: dict[str, Any]
    reefed: dict[str, Any]
    unreefed: dict[str, Any]

    componentes: tuple[TuboSpec | MassaPontualSpec, ...] = ()
    coifa: CoifaSpec | None = None
    aleta: AletaSpec | None = None
    geometria_medida: GeometriaMedidaSpec | None = None
    limites: LimitesSeguranca = field(default_factory=LimitesSeguranca)

    def __post_init__(self) -> None:
        if not self.nome or not self.nome.strip():
            raise ValueError("FogueteSpec.nome não pode ser vazio.")
        _exigir_positivo(f"FogueteSpec('{self.nome}')", raio=self.raio)
        tem_calculado = bool(self.componentes and self.coifa is not None and self.aleta is not None)
        if not tem_calculado and self.geometria_medida is None:
            raise ValueError(
                f"FogueteSpec('{self.nome}'): forneça os dados do modo 'calculado' "
                "(componentes, coifa, aleta) e/ou do modo 'medido' (geometria_medida)."
            )
