"""Tipos de componente (specs de entrada).

Modo C (híbrido):
  - TuboSpec:         massa = V·densidade + massa_extra
  - MassaPontualSpec: massa = valor fixo

Unidades: SI (m, kg, kg/m³). Ordem: nariz → cauda.

A lista concreta de componentes de cada foguete fica em
`configs/foguetes/<nome>/corpo.py`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TuboSpec:
    """Cilindro oco. Se espessura = raio_externo, é maciço."""
    nome: str
    raio_externo: float
    espessura: float           # ← era raio_interno
    comprimento: float
    posicao: float
    densidade: float
    massa_extra: float = 0.0

    @property
    def raio_interno(self) -> float:
        return self.raio_externo - self.espessura


@dataclass(frozen=True)
class MassaPontualSpec:
    """Componente sem geometria cilíndrica simples."""
    nome: str
    massa: float
    posicao: float
    raio_equivalente: float
    comprimento: float