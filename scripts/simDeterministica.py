"""Simulação determinística do Hefesto: ajuste os parâmetros no topo ou passe via CLI."""
from __future__ import annotations

import json
from datetime import datetime

from rocketpy import Flight

import src.viz  # noqa: F401 — configura backend antes de qualquer plot
from configs import HEFESTO, IREC, MOTOR_IREC
from src.ambiente import build_irec
from src.modelos import ModoFoguete, build_rocket
from src.paths import RESULTADOS
from src.specs import MotorSpec

# ============================================================
#  AQUI VOCÊ AJUSTA (uso direto na IDE)
# ============================================================
MODO_FOGUETE: ModoFoguete = "calculado"   # "calculado" | "medido"
TIPO_ALETAS: str = "freeform"             # "freeform" | "trapezio"
FATOR_EMPUXO: float = 1.00
FATOR_ARRASTO: float = 1.00
SALVAR_JSON: bool = True

# --- Motor ---
# None ou "oficial" → MOTOR_IREC puro
# Presets de motor_variacoes.py: "throat_estreito", "throat_largo", "core_uniforme", "core_fwd_menor"
USAR_VARIACAO_MOTOR: str | None = None
# ============================================================


def _resolver_motor(variacao: str | None) -> MotorSpec:
    """Retorna o `MotorSpec` correspondente à variação escolhida."""
    if variacao is None or variacao == "oficial":
        return MOTOR_IREC

    from configs.foguetes.hefesto.motor_variacoes import VARIACOES

    if variacao not in VARIACOES:
        disponiveis = ", ".join(VARIACOES.keys())
        raise ValueError(
            f"Variação '{variacao}' não existe. Disponíveis: {disponiveis}"
        )
    return VARIACOES[variacao]


def main(
    *,
    modo: ModoFoguete | None = None,
    variacao_motor: str | None = None,
    fator_empuxo: float | None = None,
    fator_arrasto: float | None = None,
    salvar_json: bool | None = None,
) -> None:
    modo_eff: ModoFoguete = modo if modo is not None else MODO_FOGUETE
    var_eff = variacao_motor if variacao_motor is not None else USAR_VARIACAO_MOTOR
    fe_eff = fator_empuxo if fator_empuxo is not None else FATOR_EMPUXO
    fa_eff = fator_arrasto if fator_arrasto is not None else FATOR_ARRASTO
    salvar_eff = salvar_json if salvar_json is not None else SALVAR_JSON

    motor_spec = _resolver_motor(var_eff)

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
                "variacao_motor": var_eff or "oficial",
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
