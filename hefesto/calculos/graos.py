"""Cálculo de propriedades de um stack de grãos (BATES)."""
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class Grao:
    id: int
    massa: float       # kg
    length: float      # m
    core: float        # m (diâmetro do canal)
    web: float         # m (espessura do propelente)

GRAOS = [
    Grao(1, 1.748, 0.15, 0.041, 0.029),
    Grao(2, 1.748, 0.15, 0.041, 0.029),
    Grao(3, 1.748, 0.15, 0.041, 0.029),
    Grao(4, 1.748, 0.15, 0.041, 0.029),
    Grao(5, 1.480, 0.15, 0.054, 0.022),
    Grao(6, 1.480, 0.15, 0.054, 0.022),
]

@dataclass
class ResultadoGraos:
    massa_total: float
    volume_total: float
    densidade_media: float
    comprimento_total: float
    cg_total: float
    raio_interno_medio: float
    raio_externo_medio: float


def calcular_graos(graos: list[Grao]) -> ResultadoGraos:
    massa_total = volume_total = momento = 0.0
    z = 0.0
    soma_r_i = soma_r_e = 0.0

    for g in graos:
        r_i = g.core / 2
        r_e = (g.core + 2 * g.web) / 2
        vol = math.pi * (r_e**2 - r_i**2) * g.length
        massa_total += g.massa
        volume_total += vol
        momento += g.massa * (z + g.length / 2)
        soma_r_i += r_i
        soma_r_e += r_e
        z += g.length

    n = len(graos)
    return ResultadoGraos(
        massa_total=massa_total,
        volume_total=volume_total,
        densidade_media=massa_total / volume_total,
        comprimento_total=z,
        cg_total=momento / massa_total,
        raio_interno_medio=soma_r_i / n,
        raio_externo_medio=soma_r_e / n,
    )


def main() -> None:
    r = calcular_graos(GRAOS)
    print(f"Massa total:       {r.massa_total:.3f} kg")
    print(f"Densidade média:   {r.densidade_media:.1f} kg/m³")
    print(f"Comprimento total: {r.comprimento_total:.3f} m")
    print(f"CG do stack:       {r.cg_total:.4f} m")
    print(f"r_i médio:         {r.raio_interno_medio:.5f} m")
    print(f"r_e médio:         {r.raio_externo_medio:.5f} m")


if __name__ == "__main__":
    main()