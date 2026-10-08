# hefesto/parsers/openmotor.py
"""Parser para arquivos .ric do OpenMotor.

Lê o YAML e converte para dataclasses de especificação de motor.
Unidades: SI (m, kg, Pa, s).

O .ric do OpenMotor tem a estrutura:
    data:
      config: {...}
      grains: [...]
      nozzle: {...}
      propellant: {...}
    type: ...
    version: ...
Todos os dados de interesse estão sob `data`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ----------------------------------------------------------------------
# Dataclasses de especificação
# ----------------------------------------------------------------------
@dataclass
class RicGrainSpec:
    type: str
    length: float
    diameter: float
    core_diameter: float
    inhibited_ends: str = "Neither"


@dataclass
class RicNozzleSpec:
    throat: float
    exit: float
    efficiency: float = 1.0
    conv_angle: float = 45.0
    div_angle: float = 15.0
    throat_length: float = 0.0
    erosion_coeff: float = 0.0
    slag_coeff: float = 0.0


@dataclass
class RicPropellantSpec:
    name: str
    density: float
    tabs: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class RicMotorSpec:
    grains: List[RicGrainSpec]
    nozzle: RicNozzleSpec
    propellant: RicPropellantSpec
    config: Dict[str, Any] = field(default_factory=dict)
    version: Optional[tuple] = None
    file_type: Optional[int] = None

    @property
    def total_propellant_length(self) -> float:
        return sum(g.length for g in self.grains)

    @property
    def num_grains(self) -> int:
        return len(self.grains)

    def resumo(self) -> str:
        linhas = [
            f"Motor: {self.propellant.name}",
            f"  Grãos: {self.num_grains} × {self.grains[0].type}",
            f"  Comprimento total propelente: {self.total_propellant_length:.3f} m",
            f"  Diâmetro externo: {self.grains[0].diameter:.5f} m",
            f"  Core(s): {[g.core_diameter for g in self.grains]} m",
            f"  Tubeira: garganta={self.nozzle.throat:.4f} m, saída={self.nozzle.exit:.4f} m",
            f"  Densidade propelente: {self.propellant.density:.1f} kg/m³",
        ]
        return "\n".join(linhas)


# ----------------------------------------------------------------------
# Loader YAML seguro para OpenMotor
# ----------------------------------------------------------------------
class OpenMotorLoader(yaml.SafeLoader):
    """SafeLoader que entende as tags específicas do OpenMotor."""


def _openmotor_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    if node.tag == "tag:yaml.org,2002:python/object/apply:uilib.fileIO.fileTypes":
        seq = loader.construct_sequence(node)
        return seq[0] if seq else None

    if node.tag == "tag:yaml.org,2002:python/tuple":
        return tuple(loader.construct_sequence(node))

    raise yaml.constructor.ConstructorError(
        None, None, f"Tag não suportada: {node.tag}", node.start_mark
    )


OpenMotorLoader.add_constructor(
    "tag:yaml.org,2002:python/object/apply:uilib.fileIO.fileTypes",
    _openmotor_constructor,
)
OpenMotorLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    _openmotor_constructor,
)


# ----------------------------------------------------------------------
# Helpers de leitura defensiva
# ----------------------------------------------------------------------
def _primeiro(d: dict, *chaves, contexto: str, default=None, obrigatorio: bool = True):
    for k in chaves:
        if k in d and d[k] is not None:
            return d[k]
    if not obrigatorio and default is not None:
        return default
    disponiveis = ", ".join(sorted(d.keys())) or "(vazio)"
    raise KeyError(
        f"Nenhuma das chaves {chaves} encontrada em {contexto}.\n"
        f"  Chaves disponíveis: {disponiveis}"
    )


# ----------------------------------------------------------------------
# API principal
# ----------------------------------------------------------------------
def carregar_ric(caminho: str | Path) -> RicMotorSpec:
    """Lê um arquivo .ric e retorna um MotorSpec.

    Parameters
    ----------
    caminho : str | Path
        Caminho para o arquivo .ric.

    Returns
    -------
    RicMotorSpec
        Especificação completa do motor.
    """
    caminho = Path(caminho)
    with caminho.open("r", encoding="utf-8") as f:
        raiz = yaml.load(f, Loader=OpenMotorLoader)

    if not isinstance(raiz, dict):
        raise TypeError(f"Raiz do .ric não é dict (é {type(raiz)}).")

    # O conteúdo útil está sob 'data'
    dados = raiz.get("data")
    if not isinstance(dados, dict):
        raise KeyError(
            f"Seção 'data' ausente/inválida. Chaves raiz: {sorted(raiz.keys())}"
        )

    # --- Grãos ---
    grains_raw = dados.get("grains")
    if not grains_raw:
        raise KeyError(
            f"Seção 'grains' ausente/vazia em 'data'. "
            f"Chaves de 'data': {sorted(dados.keys())}"
        )

    grains: List[RicGrainSpec] = []
    for i, g in enumerate(grains_raw):
        ctx = f"data.grains[{i}].properties"
        props = g.get("properties")
        if not isinstance(props, dict):
            raise KeyError(f"Seção '{ctx}' ausente/inválida.")

        grains.append(
            RicGrainSpec(
                type=g.get("type", "BATES"),
                length=float(_primeiro(props, "length", contexto=ctx)),
                diameter=float(_primeiro(props, "diameter", contexto=ctx)),
                core_diameter=float(
                    _primeiro(props, "coreDiameter", "core_diameter", contexto=ctx)
                ),
                inhibited_ends=_primeiro(
                    props, "inhibitedEnds", "inhibited_ends",
                    contexto=ctx, default="Neither", obrigatorio=False,
                ),
            )
        )

    # --- Tubeira ---
    nz = dados.get("nozzle")
    if not isinstance(nz, dict) or not nz:
        raise KeyError(
            f"Seção 'nozzle' ausente/vazia em 'data'. "
            f"Chaves de 'data': {sorted(dados.keys())}"
        )

    nozzle = RicNozzleSpec(
        throat=float(_primeiro(nz, "throat", "throatDiameter", contexto="data.nozzle")),
        exit=float(_primeiro(nz, "exit", "exitDiameter", contexto="data.nozzle")),
        efficiency=float(_primeiro(
            nz, "efficiency", contexto="data.nozzle", default=1.0, obrigatorio=False,
        )),
        conv_angle=float(_primeiro(
            nz, "convAngle", "conv_angle", contexto="data.nozzle",
            default=45.0, obrigatorio=False,
        )),
        div_angle=float(_primeiro(
            nz, "divAngle", "div_angle", contexto="data.nozzle",
            default=15.0, obrigatorio=False,
        )),
        throat_length=float(_primeiro(
            nz, "throatLength", "throat_length", contexto="data.nozzle",
            default=0.0, obrigatorio=False,
        )),
        erosion_coeff=float(_primeiro(
            nz, "erosionCoeff", "erosion_coeff", contexto="data.nozzle",
            default=0.0, obrigatorio=False,
        )),
        slag_coeff=float(_primeiro(
            nz, "slagCoeff", "slag_coeff", contexto="data.nozzle",
            default=0.0, obrigatorio=False,
        )),
    )

    # --- Propelente ---
    prop = dados.get("propellant")
    if not isinstance(prop, dict):
        raise KeyError(
            f"Seção 'propellant' ausente/inválida em 'data'. "
            f"Chaves de 'data': {sorted(dados.keys())}"
        )

    propellant = RicPropellantSpec(
        name=prop.get("name", "Desconhecido"),
        density=float(_primeiro(prop, "density", contexto="data.propellant")),
        tabs=prop.get("tabs", []),
    )

    return RicMotorSpec(
        grains=grains,
        nozzle=nozzle,
        propellant=propellant,
        config=dados.get("config", {}),
        version=raiz.get("version"),
        file_type=raiz.get("type"),
    )

# ======================================================================
# Conversor: RicMotorSpec → hefesto.MotorSpec
# ======================================================================
# Adicione no topo do arquivo, junto aos outros imports:
#
#     from configs.motor_spec import GrainSpec as HefGrainSpec
#     from configs.motor_spec import MotorSpec as HefMotorSpec
#
# Como o módulo usa `from __future__ import annotations`, o import pode
# ficar dentro da função para evitar dependência circular se motor_spec
# um dia importar algo do parser.


def motor_spec_do_ric(
    ric_path: str | Path,
    *,
    thrust_curve_path: str,
    case_inner_radius: float,
    case_wall_thickness: float,
    case_density: float = 2700.0,     # alumínio 6063-T5
    grain_separation: float = 0.010,
    nozzle_position: float,
    case_length: float | None = None,
    margin_nozzle_side: float = 0.075,
    margin_forward_side: float = 0.075,
    dry_mass: float | None = None,
    dry_mass_extra: float = 0.0,
    nozzle_mass: float = 0.0,
    dry_inertia_override: tuple[float, float, float] | None = None,
    nome: str | None = None,
):
    """Converte um .ric do OpenMotor em MotorSpec do hefesto.

    Parâmetros do .ric (grãos, tubeira, propelente) são lidos automaticamente.
    O que o .ric não carrega — carcaça, separação entre grãos, posição da
    tubeira, curva de empuxo — precisa vir como argumento.

    Returns
    -------
    MotorSpec (de configs.motor_spec)
    """
    from configs.motor.spec import GrainSpec as HefGrainSpec
    from configs.motor.spec import MotorSpec as HefMotorSpec

    ric = carregar_ric(ric_path)

    # --- Grãos: converter diâmetro → raio ---
    grains_hef = tuple(
        HefGrainSpec(
            length=g.length,
            outer_radius=g.diameter / 2.0,
            inner_radius=g.core_diameter / 2.0,
        )
        for g in ric.grains
    )

    # --- Nome do motor ---
    # Preferência: argumento explícito > nome do propelente no .ric
    nome_final = nome or ric.propellant.name

    return HefMotorSpec(
        nome=nome_final,
        ric_path=str(ric_path),  # ← NOVO
        thrust_curve_path=str(thrust_curve_path) if thrust_curve_path else None,

        case_inner_radius=case_inner_radius,
        case_wall_thickness=case_wall_thickness,
        case_density=case_density,

        grains=grains_hef,
        grain_separation=grain_separation,
        propellant_density=ric.propellant.density,

        nozzle_position=nozzle_position,
        nozzle_exit_radius=ric.nozzle.exit / 2.0,
        throat_radius=ric.nozzle.throat / 2.0,

        case_length=case_length,
        margin_nozzle_side=margin_nozzle_side,
        margin_forward_side=margin_forward_side,

        dry_mass=dry_mass,
        dry_mass_extra=dry_mass_extra,
        nozzle_mass=nozzle_mass,

        dry_inertia_override=dry_inertia_override,
    )
# ----------------------------------------------------------------------
# Teste rápido
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m hefesto.parsers.openmotor <arquivo.ric>")
        sys.exit(1)

    spec = carregar_ric(sys.argv[1])
    print(spec.resumo())