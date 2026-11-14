"""Simulação determinística do Hefesto: ajuste os parâmetros no topo ou passe via CLI."""
from __future__ import annotations

import json
from datetime import datetime

from rocketpy import Flight

from configs import HEFESTO, IREC, MOTOR_IREC
from src.caminhos import RESULTADOS
from src.especificacoes import MotorSpec
from src.simulacao.ambiente import build_irec
from src.simulacao.construtor_foguete import ModoFoguete, build_rocket

# ============================================================
#  AQUI VOCÊ AJUSTA (uso direto na IDE)
# ============================================================
MODO_FOGUETE: ModoFoguete = "calculado"   # "calculado" | "medido"
TIPO_ALETAS: str = "freeform"             # "freeform" | "trapezio"
FATOR_EMPUXO: float = 1.00
FATOR_ARRASTO: float = 1.00
SALVAR_JSON: bool = True

# --- Motor ---
# None → usa MOTOR_IREC oficial (ou passe um MotorSpec customizado)
MOTOR: MotorSpec | None = None
# ============================================================


def main(
    *,
    modo: ModoFoguete | None = None,
    motor: MotorSpec | None = None,
    fator_empuxo: float | None = None,
    fator_arrasto: float | None = None,
    salvar_json: bool | None = None,
) -> None:
    modo_eff: ModoFoguete = modo if modo is not None else MODO_FOGUETE
    motor_spec: MotorSpec = motor if motor is not None else (MOTOR or MOTOR_IREC)
    fe_eff = fator_empuxo if fator_empuxo is not None else FATOR_EMPUXO
    fa_eff = fator_arrasto if fator_arrasto is not None else FATOR_ARRASTO
    salvar_eff = salvar_json if salvar_json is not None else SALVAR_JSON

    foguete = build_rocket(
        HEFESTO,
        modo=modo_eff,
        motor_spec=motor_spec,
        tipo_aletas=TIPO_ALETAS,
        fator_empuxo=fe_eff,
        fator_arrasto=fa_eff,
    )
    env = build_irec()
    voo = Flight(rocket=foguete.rocket, environment=env, **IREC)

    apogee_agl = voo.apogee - env.elevation

    print()
    print("=" * 54)
    print(f"Foguete:          {HEFESTO.nome} (modo={modo_eff})")
    print(f"Motor:            {motor_spec.nome}")
    print(f"Tipo de aletas:   {TIPO_ALETAS}")
    print(f"Massa seca:       {foguete.rocket.mass:.3f} kg")
    print(f"Fator empuxo:     {fe_eff:.3f}")
    print(f"Impulso total:    {foguete.motor.total_impulse:.1f} N·s")
    print(f"Fator arrasto:    {fa_eff:.3f}")
    print("-" * 54)
    print(f"Apogeu AGL:       {apogee_agl:.1f} m")
    print(f"Margem mínima:    {voo.min_stability_margin:.3f} cal")
    print("=" * 54)

    if salvar_eff:
        diags = [
            {
                "nome": x.nome,
                "valor": x.valor,
                "ok": x.ok,
                "detalhe": x.detalhe,
            }
            for x in foguete.motor_derivado.diagnosticos
        ]

        resultado = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "configuracao": {
                "modo_foguete": modo_eff,
                "tipo_aletas": TIPO_ALETAS,
                "fator_empuxo": fe_eff,
                "fator_arrasto": fa_eff,
                "motor": motor_spec.nome,
            },
            "motor_spec": motor_spec.to_dict(),
            "motor_derivado": foguete.motor_derivado.to_dict(),
            "resultado": {
                "apogee_agl_m": apogee_agl,
                "apogee_msl_m": voo.apogee,
                "min_stability_margin_cal": voo.min_stability_margin,
                "total_impulse_Ns": foguete.motor.total_impulse,
            },
            "diagnosticos_motor": diags,
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        nome = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        destino = RESULTADOS / nome
        with destino.open("w", encoding="utf-8") as fp:
            json.dump(resultado, fp, indent=2, ensure_ascii=False)
        print(f"\nJSON salvo em: {destino}")


if __name__ == "__main__":
    main()
