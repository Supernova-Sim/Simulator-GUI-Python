# hefesto/parsers/openmotor.py
"""Parser para arquivos .ric do OpenMotor.

Lê o YAML e converte para dataclasses de especificação de motor.
Unidades: SI (m, kg, Pa, s).
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
class GrainSpec:
    type: str
    length: float
    diameter: float
    core_diameter: float
    inhibited_ends: str = "Neither"


@dataclass
class NozzleSpec:
    throat: float
    exit: float
    efficiency: float = 1.0
    conv_angle: float = 45.0
    div_angle: float = 15.0
    throat_length: float = 0.0
    erosion_coeff: float = 0.0
    slag_coeff: float = 0.0


@dataclass
class PropellantSpec:
    name: str
    density: float
    tabs: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class MotorSpec:
    grains: List[GrainSpec]
    nozzle: NozzleSpec
    propellant: PropellantSpec
    config: Dict[str, Any] = field(default_factory=dict)
    version: Optional[tuple] = None

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
    """Constrói objetos para tags do OpenMotor."""
    if node.tag == "tag:yaml.org,2002:python/object/apply:uilib.fileIO.fileTypes":
        # Ex.: type: !!python/object/apply:uilib.fileIO.fileTypes
        #        - 3
        # Retorna o valor 3 (enum fileTypes)
        seq = loader.construct_sequence(node)
        return seq[0] if seq else None

    if node.tag == "tag:yaml.org,2002:python/tuple":
        # Ex.: version: !!python/tuple [0, 6, 1]
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
def _get_obrigatorio(d: dict, chave: str, contexto: str) -> Any:
    if chave not in d:
        disponiveis = ", ".join(sorted(d.keys())) or "(vazio)"
        raise KeyError(
            f"Chave obrigatória '{chave}' ausente em {contexto}.\n"
            f"  Chaves disponíveis: {disponiveis}"
        )
    return d[chave]


def _get_float(d: dict, chave: str, contexto: str, default: float | None = None) -> float:
    if chave in d:
        return float(d[chave])
    if default is not None:
        return default
    disponiveis = ", ".join(sorted(d.keys())) or "(vazio)"
    raise KeyError(
        f"Chave obrigatória '{chave}' ausente em {contexto}.\n"
        f"  Chaves disponíveis: {disponiveis}"
    )


# ----------------------------------------------------------------------
# API principal
# ----------------------------------------------------------------------
def carregar_ric(caminho: str | Path) -> MotorSpec:
    """Lê um arquivo .ric e retorna um MotorSpec."""
    caminho = Path(caminho)
    with caminho.open("r", encoding="utf-8") as f:
        dados = yaml.load(f, Loader=OpenMotorLoader)

    if not isinstance(dados, dict):
        raise TypeError(f"Conteúdo raiz do .ric não é um dicionário (é {type(dados)}).")

    # --- Grãos ---
    grains_raw = dados.get("grains")
    if not grains_raw:
        raise KeyError("Seção 'grains' ausente ou vazia no .ric.")

    grains: List[GrainSpec] = []
    for i, g in enumerate(grains_raw):
        ctx = f"grains[{i}].properties"
        props = g.get("properties")
        if not isinstance(props, dict):
            raise KeyError(f"Seção '{ctx}' ausente ou inválida.")

        # Aceita camelCase e snake_case
        def pega(*nomes, default=None):
            for n in nomes:
                if n in props:
                    return props[n]
            if default is not None:
                return default
            disponiveis = ", ".join(sorted(props.keys()))
            raise KeyError(
                f"Nenhuma das chaves {nomes} encontrada em {ctx}.\n"
                f"  Chaves disponíveis: {disponiveis}"
            )

        grains.append(
            GrainSpec(
                type=g.get("type", "BATES"),
                length=float(pega("length")),
                diameter=float(pega("diameter")),
                core_diameter=float(pega("coreDiameter", "core_diameter")),
                inhibited_ends=pega("inhibitedEnds", "inhibited_ends", default="Neither"),
            )
        )

    # --- Tubeira ---
    nz = dados.get("nozzle")
    if not isinstance(nz, dict):
        raise KeyError("Seção 'nozzle' ausente ou inválida no .ric.")
    print(f"[debug] nozzle keys: {sorted(nz.keys())}")  # remover depois

    nozzle = NozzleSpec(
        throat=_get_float(nz, "throat", "nozzle"),
        exit=_get_float(nz, "exit", "nozzle"),
        efficiency=_get_float(nz, "efficiency", "nozzle", default=1.0),
        conv_angle=_get_float(nz, "convAngle", "nozzle", default=45.0),
        div_angle=_get_float(nz, "divAngle", "nozzle", default=15.0),
        throat_length=_get_float(nz, "throatLength", "nozzle", default=0.0),
        erosion_coeff=_get_float(nz, "erosionCoeff", "nozzle", default=0.0),
        slag_coeff=_get_float(nz, "slagCoeff", "nozzle", default=0.0),
    )

    # --- Propelente ---
    prop = dados.get("propellant")
    if not isinstance(prop, dict):
        raise KeyError("Seção 'propellant' ausente ou inválida no .ric.")

    propellant = PropellantSpec(
        name=prop.get("name", "Desconhecido"),
        density=_get_float(prop, "density", "propellant"),
        tabs=prop.get("tabs", []),
    )

    return MotorSpec(
        grains=grains,
        nozzle=nozzle,
        propellant=propellant,
        config=dados.get("config", {}),
        version=dados.get("version"),
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