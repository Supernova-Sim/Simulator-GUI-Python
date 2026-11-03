---
component_id: 2
component_name: Simulation and Analysis Scripts
---

# Simulation and Analysis Scripts

## Component Description

Standalone simulation workflows including deterministic flights, sweeps, and Monte Carlo runs.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/scripts/simDeterministica.py (lines 47-125)
```
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
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/scripts/monteCarloIrec.py (lines 38-103)
```
def main(n_simulacoes: int = 100) -> None:
    # ---------------------------------------------------------------
    # 1. Determinístico (base para cada Stochastic*)
    # ---------------------------------------------------------------
    det = build_rocket(HEFESTO, modo="medido", tipo_aletas="trapezio")
    env_det = build_irec()

    voo_det = Flight(rocket=det.rocket, environment=env_det, **IREC)

    # ---------------------------------------------------------------
    # 2. Componentes estocásticos
    # ---------------------------------------------------------------
    motor_est = StochasticSolidMotor(solid_motor=det.motor, **MOTOR_E)

    foguete_est = StochasticRocket(rocket=det.rocket, **FOGUETE_E)
    foguete_est.add_motor(motor_est, position=MOTOR_POS_E)

    coifa_est = StochasticNoseCone(nosecone=det.nosecone, **COIFA_E)
    aletas_est = StochasticTrapezoidalFins(trapezoidal_fins=det.fins, **ALETAS_E)
    rail_est = StochasticRailButtons(rail_buttons=det.rail_buttons, **RAIL_BUTTONS_E)

    unreefed_est = StochasticParachute(parachute=det.unreefed, **UNREEFED_E)
    reefed_est = StochasticParachute(parachute=det.reefed, **REEFED_E)

    foguete_est.add_nose(coifa_est, position=COIFA_POS_E)
    foguete_est.add_trapezoidal_fins(aletas_est, position=ALETAS_POS_E)
    foguete_est.set_rail_buttons(
        rail_est, lower_button_position=LOWER_BUTTON_POSITION_E
    )
    foguete_est.add_parachute(unreefed_est)
    foguete_est.add_parachute(reefed_est)

    # ---------------------------------------------------------------
    # 3. Ambiente e voo estocásticos
    # ---------------------------------------------------------------
    env_ens = build_irec_ensemble()
    env_est = StochasticEnvironment(
        environment=env_ens,
        ensemble_member=list(range(env_ens.num_ensemble_members)),
        **IREC_ENSEMBLE_E,
    )

    voo_est = StochasticFlight(flight=voo_det, **IREC_E)

    # ---------------------------------------------------------------
    # 4. Monte Carlo
    # ---------------------------------------------------------------
    data_collector = {
        "apogee_agl": lambda f: f.apogee - f.env.elevation,
    }

    mc = MonteCarlo(
        filename=str(RESULTADOS / "irec"),
        environment=env_est,
        rocket=foguete_est,
        flight=voo_est,
        data_collector=data_collector,
    )

    mc.simulate(
        number_of_simulations=n_simulacoes,
        append=False,
        parallel=True,
        n_workers=4,
    )
    mc.all_info()
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/scripts/varredura.py (lines 47-90)
```
def main() -> None:
    total = len(FATORES_EMPUXO) * len(FATORES_ARRASTO)
    print(f"Total de simulações: {total} (modo={MODO_FOGUETE})")
    if total == 0:
        raise SystemExit("Nenhum fator definido.")

    linhas: list[dict[str, float]] = []
    i = 0
    for fe in FATORES_EMPUXO:
        for fa in FATORES_ARRASTO:
            i += 1
            linha = simular(float(fe), float(fa))
            linhas.append(linha)
            print(
                f"[{i:>3}/{total}] "
                f"empuxo={linha['fator_empuxo']:.3f}  "
                f"arrasto={linha['fator_arrasto']:.3f}  →  "
                f"apogeu AGL={linha['apogee_agl']:>8.1f} m  "
                f"margem={linha['margem_min']:.3f} cal"
            )

    destino = RESULTADOS / ARQUIVO_SAIDA
    with destino.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "configuracao": {
            "modo_foguete": MODO_FOGUETE,
            "tipo_aletas": TIPO_ALETAS,
            "n_fatores_empuxo": len(FATORES_EMPUXO),
            "n_fatores_arrasto": len(FATORES_ARRASTO),
        },
        "motor_spec": MOTOR_IREC.to_dict(),
        "motor_derivado": derivar_motor(MOTOR_IREC).to_dict(),
    }
    meta_path = RESULTADOS / ARQUIVO_SAIDA.replace(".csv", "_meta.json")
    with meta_path.open("w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)

    print(f"\nCSV:  {destino}  ({len(linhas)} linhas)")
    print(f"Meta: {meta_path}")
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/scripts/analisar_motor.py (lines 391-427)
```
def main() -> None:
    p = argparse.ArgumentParser(
        description="Analisa CSV de varredura de motor"
    )
    p.add_argument("--csv", type=Path, default=None,
                   help="CSV específico (default: mais recente)")
    p.add_argument("--fs-min", type=float, default=None,
                   help="Filtro FS mínimo")
    p.add_argument("--objetivo", default="impulse_Ns",
                   help="Coluna para maximizar (default: impulse_Ns)")
    p.add_argument("--top", type=int, default=10,
                   help="Quantos mostrar no top (default: 10)")

    args = p.parse_args()

    regs = carregar_varredura(args.csv)
    resumo(regs)

    viaveis = filtrar(regs, fs_min=args.fs_min)
    imprimir_top(viaveis, objetivo=args.objetivo, n=args.top)

    otimo = achar_otimo(regs, objetivo=args.objetivo, fs_min=args.fs_min)
    if otimo:
        print()
        print("=" * 70)
        print(f"  ÓTIMO VIÁVEL  ({args.objetivo})")
        print("=" * 70)
        for p_name in params_do_registro(regs):
            print(f"  {p_name:<40} {otimo[p_name]}")
        print(f"  {'impulse_Ns':<40} {otimo['impulse_Ns']:.2f}")
        print(f"  {'p0_MPa':<40} {otimo['p0_MPa']:.3f}")
        print(f"  {'kn':<40} {otimo['kn']:.1f}")
        print(f"  {'mass_flux':<40} {otimo['mass_flux']:.1f}")
        print(f"  {'fs_carcaca':<40} {otimo['fs_carcaca']:.3f}")
    else:
        print()
        print("⚠ Nenhum ponto viável com os filtros aplicados.")
```


## Source Files:

- `scripts/analisar_motor.py`
- `scripts/monteCarloIrec.py`
- `scripts/simDeterministica.py`
- `scripts/varredura.py`
- `scripts/varredura_motor.py`

