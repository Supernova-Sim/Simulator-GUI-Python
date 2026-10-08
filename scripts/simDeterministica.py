"""Teste único: ajuste os fatores no topo e rode."""
from rocketpy import Flight

from hefesto.ambiente import build_irec
from hefesto.modelos import build_rocket
from configs.voo import IREC
from configs.especificacao import ALETA_IREC

USAR_SPEC_ALETA = True
TIPO_ALETAS   = "freeform"   # "freeform" ou "trapezio"
FATOR_EMPUXO  = 1.00         # 1.00 = nominal
FATOR_ARRASTO = 1.00         # 1.00 = nominal



def main() -> None:
    foguete = build_rocket(
        tipo_aletas=TIPO_ALETAS,
        spec_aleta=ALETA_IREC if USAR_SPEC_ALETA else None,
        fator_empuxo=FATOR_EMPUXO,
        fator_arrasto=FATOR_ARRASTO,
    )

    env = build_irec()
    voo = Flight(rocket=foguete.rocket, environment=env, **IREC)

    apogee_agl = voo.apogee - env.elevation

    print()
    print("=" * 50)
    print(f"Tipo de aletas:   {TIPO_ALETAS}")
    print(f"Fator empuxo:     {FATOR_EMPUXO:.3f} ")
    print(f"Empuxo: {foguete.motor.total_impulse:.3f}")
    print(f"Fator arrasto:    {FATOR_ARRASTO:.3f}")
    print("-" * 50)
    print(f"Apogeu AGL:       {apogee_agl:.1f} m")
    print(f"Margem mínima:    {voo.min_stability_margin:.3f} cal")
    print("=" * 50)


if __name__ == "__main__":
    main()