"""Teste único: ajuste os fatores no topo e rode."""
import json
from datetime import datetime

from rocketpy import Flight

from src.ambiente import build_irec
from src.modelos import build_rocket
from src.paths import RESULTADOS

from configs import IREC, ALETA_IREC, MOTOR_IREC

USAR_SPEC_ALETA = True
TIPO_ALETAS     = "freeform"
FATOR_EMPUXO    = 1.00
FATOR_ARRASTO   = 1.00
SALVAR_JSON     = True


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
    print(f"Fator empuxo:     {FATOR_EMPUXO:.3f}")
    print(f"Empuxo:           {foguete.motor.total_impulse:.3f} N.s")
    print(f"Fator arrasto:    {FATOR_ARRASTO:.3f}")
    print("-" * 50)
    print(f"Apogeu AGL:       {apogee_agl:.1f} m")
    print(f"Margem mínima:    {voo.min_stability_margin:.3f} cal")
    print("=" * 50)

    if SALVAR_JSON:
        resultado = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "configuracao": {
                "tipo_aletas": TIPO_ALETAS,
                "usar_spec_aleta": USAR_SPEC_ALETA,
                "fator_empuxo": FATOR_EMPUXO,
                "fator_arrasto": FATOR_ARRASTO,
            },
            "motor_spec": MOTOR_IREC.to_dict(),
            "motor_derivado": foguete.motor_derivado.to_dict(),
            "resultado": {
                "apogee_agl_m": apogee_agl,
                "apogee_msl_m": voo.apogee,
                "min_stability_margin_cal": voo.min_stability_margin,
                "total_impulse_Ns": foguete.motor.total_impulse,
            },
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        nome = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        destino = RESULTADOS / nome
        with destino.open("w", encoding="utf-8") as fp:
            json.dump(resultado, fp, indent=2, ensure_ascii=False)
        print(f"\nJSON salvo em: {destino}")


if __name__ == "__main__":
    main()