"""Cálculo de inércia seca do foguete a partir de lista de componentes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Componente:
    nome: str
    m: float        # kg
    x: float        # m (posição do CG no eixo do foguete)
    r_e: float      # m (raio externo)
    r_i: float      # m (raio interno; 0 se maciço)
    l: float        # m (comprimento)

COMPONENTES = [
    Componente("Coifa", 1.300, 0.2795, 0.079, 0.076, 0.450),
    Componente("Módulo Aviônica", 1.4593, 0.7200, 0.079, 0.076, 0.540),
    Componente("Módulo Payload", 1.2161, 1.2150, 0.079, 0.076, 0.450),
    Componente("Módulo Propulsão", 2.4593, 1.8950, 0.079, 0.076, 0.910),
    Componente("Módulo Aletas", 1.0810, 2.5500, 0.079, 0.076, 0.400),
    Componente("Junção Aviônica/Payload", 0.7583, 0.9900, 0.076, 0.073, 0.200),
    Componente("Junção Payload/Propulsão", 0.7583, 1.4400, 0.076, 0.073, 0.200),
    Componente("Junção Propulsão/Aletas", 0.7583, 2.3500, 0.076, 0.073, 0.200),
    Componente("Fixador Superior 1", 0.1384, 0.9400, 0.073, 0.063, 0.012),
    Componente("Fixador Inferior 1", 0.1384, 1.0400, 0.073, 0.063, 0.012),
    Componente("Fixador Superior 2", 0.1384, 1.3900, 0.073, 0.063, 0.012),
    Componente("Anel centralizador inf 1", 0.1448, 2.3000, 0.073, 0.0625, 0.012),
    Componente("Anel centralizador sup 1", 0.1448, 2.4000, 0.073, 0.0625, 0.012),
    Componente("Anel centralizador sup 2", 0.3215, 2.6225, 0.076, 0.057, 0.015),
    Componente("Anel centralizador médio 2", 0.3215, 2.6625, 0.076, 0.057, 0.015),
    Componente("Anel centralizador inf 2", 0.3215, 2.7025, 0.076, 0.057, 0.015),
    Componente("Anteparo Recuperação", 0.5879, 0.6680, 0.076, 0.000, 0.012),
    Componente("Anteparo Inferior", 0.9040, 1.4900, 0.073, 0.000, 0.020),
    Componente("Paraquedas unreefed", 0.6500, 0.4300, 0.070, 0.000, 0.300),
    Componente("Paraquedas reefed", 0.6500, 0.4300, 0.070, 0.000, 0.300),
    Componente("Sistemas de recuperação", 1.7670, 0.6300, 0.030, 0.000, 0.060),
    Componente("Aviônica", 0.7000, 0.7010, 0.050, 0.000, 0.050),
    Componente("Satélite", 1.4000, 1.2020, 0.071, 0.000, 0.300),
    Componente("Complemento de massa", 2.6000, 1.3680, 0.076, 0.000, 0.020),
    Componente("Rail Button (conjunto)", 0.0476, 1.8450, 0.020, 0.0065, 0.027),
#    Componente("Aletas (aprox. cilíndrica)", 0.8769, 2.6855, 0.158, 0.079, 0.210),
]

CG_GLOBAL = 1.294 #Analisar se isso nao deve receber o CG que está em configs/foguete

def calcular_inercia(
    componentes: list[Componente],
    cg_global: float,
) -> tuple[float, float]:
    """Retorna (I_xx, I_yy) em kg·m²."""
    I_xx = 0.0
    I_yy = 0.0
    for c in componentes:
        # inércia intrínseca transversal
        i_intr = (c.m / 12) * (3 * (c.r_e**2 + c.r_i**2) + c.l**2)
        # Steiner
        d = abs(c.x - cg_global)
        I_yy += i_intr + c.m * d**2
        # inércia longitudinal
        I_xx += 0.5 * c.m * (c.r_e**2 + c.r_i**2)
    return I_xx, I_yy


def main() -> None:
    I_xx, I_yy = calcular_inercia(COMPONENTES, CG_GLOBAL)
    print(f"I_xx (roll):       {I_xx:.3f} kg·m²")
    print(f"I_yy/I_zz (pitch): {I_yy:.3f} kg·m²")


if __name__ == "__main__":
    main()