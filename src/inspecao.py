# src/inspecao.py
"""Relatórios de inspeção e diagnóstico estrutural, balístico e de voo.

Unifica o antigo `src/dump.py` e a formatação de `centralControle/inspecionar.py`
em um módulo puro (não importa `configs/`, recebendo os objetos por argumento).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.calculos.motor import MotorDerivado, derivar_motor
from src.modelo import resolver
from src.specs import FogueteSpec, MotorSpec, TuboSpec

LARGURA = 72


def _titulo(txt: str) -> None:
    print()
    print("═" * LARGURA)
    print(f"  {txt}")
    print("═" * LARGURA)


def _sub(txt: str) -> None:
    print()
    print(f"── {txt} ──")


def _linha(label: str, valor: Any, unidade: str = "", largura: int = 30) -> None:
    if unidade:
        print(f"  {label:<{largura}} {valor} {unidade}")
    else:
        print(f"  {label:<{largura}} {valor}")


def _fmt(v: float | None, casas: int = 4, unidade: str = "") -> str:
    if v is None:
        return "(—)"
    s = f"{v:.{casas}f}"
    return f"{s} {unidade}" if unidade else s


def relatorio_motor(
    spec: MotorSpec,
    *,
    derivado: MotorDerivado | None = None,
) -> MotorDerivado:
    """Imprime especificação, propriedades derivadas e balística interna do motor."""
    d = derivado if derivado is not None else derivar_motor(spec)

    _titulo("MOTOR — SPEC & GEOMETRIA EFETIVA")
    _linha("nome", spec.nome)
    _linha("fonte", d.fonte)
    _linha("ric_path", spec.ric_path or "—")
    _linha("thrust_curve", spec.thrust_curve_path or "—")
    if spec.overrides:
        _linha("overrides ativos", f"{len(spec.overrides)} parâmetro(s)")

    _sub(f"Grãos efetivos ({len(d.grains)})")
    for i, g in enumerate(d.grains):
        print(
            f"  [{i}]  L={g.length:.4f} m   "
            f"r_o={g.outer_radius:.5f} m   "
            f"r_i={g.inner_radius:.5f} m"
        )
    _linha("separação", _fmt(spec.grain_separation * 1000, 1, "mm"))
    _linha("ρ propelente", _fmt(d.propellant_density, 1, "kg/m³"))

    _sub("Carcaça")
    _linha("raio interno", _fmt(spec.case_inner_radius * 1000, 3, "mm"))
    _linha("espessura parede", _fmt(spec.case_wall_thickness * 1000, 3, "mm"))
    _linha("ρ carcaça", _fmt(spec.case_density, 1, "kg/m³"))
    _linha("comprimento", _fmt(d.case_length, 4, "m"))
    _linha("massa seca", _fmt(d.dry_mass, 4, "kg"))

    _sub("Tubeira")
    _linha("posição", _fmt(spec.nozzle_position * 1000, 2, "mm"))
    _linha("r de saída", _fmt(d.nozzle_exit_radius * 1000, 2, "mm"))
    _linha("r da garganta", _fmt(d.throat_radius * 1000, 2, "mm"))

    _titulo("MOTOR — DERIVADO")
    _sub("Cinemática")
    _linha("burn_time", f"{d.burn_time[0]:.3f} → {d.burn_time[1]:.3f} s")
    _linha("impulso total", _fmt(d.total_impulse, 1, "N·s"))
    _linha("empuxo máximo", _fmt(d.max_thrust, 1, "N"))
    dur = d.burn_time[1] - d.burn_time[0]
    _linha("empuxo médio", _fmt(d.total_impulse / dur, 1, "N") if dur else "—")
    _linha("ISP entregue", _fmt(d.isp_entregue, 2, "s"))

    _sub("Geometria / Massas")
    _linha("massa propelente", _fmt(d.propellant_mass, 4, "kg"))
    _linha("comprimento propelente", _fmt(d.propellant_length, 4, "m"))
    _linha("stack length", _fmt(d.stack_length, 4, "m"))
    _linha("CG do propelente (local)", _fmt(d.cg_propellant, 4, "m"))
    _linha("r_i efetivo", _fmt(d.grain_inner_radius_effective * 1000, 3, "mm"))
    _linha("massa seca", _fmt(d.dry_mass, 4, "kg"))
    _linha("massa carregada", _fmt(d.mass_loaded, 4, "kg"))

    _sub("Inércia seca — Convenção RocketPy (I_11, I_22, I_33)")
    _linha("I_11 (pitch/transversal)", _fmt(d.dry_inertia[0], 6, "kg·m²"))
    _linha("I_22 (yaw/transversal)", _fmt(d.dry_inertia[1], 6, "kg·m²"))
    _linha("I_33 (roll/longitudinal)", _fmt(d.dry_inertia[2], 6, "kg·m²"))

    if d.p0_pico is not None:
        _sub("Balística interna")
        _linha("P0 de pico", _fmt(d.p0_pico / 1e6, 3, "MPa"))
        _linha("Kn de pico", _fmt(d.kn_pico, 1))
        _linha("mass flux de pico", _fmt(d.mass_flux_pico, 3, "kg/(m²·s)"))

    return d


def relatorio_motor_variacoes(
    variacoes: Mapping[str, MotorSpec],
    params_livres: set[str] | None = None,
) -> None:
    """Imprime tabela comparativa lado a lado para um dicionário de variações de motor."""
    _titulo("VARIAÇÕES DO MOTOR")

    if params_livres is not None:
        _sub(f"Parâmetros livres ({len(params_livres)})")
        for p in sorted(params_livres):
            print(f"    {p}")

    _sub("Comparativo")
    cab = (
        f"  {'variação':<20} "
        f"{'impulse':>10} "
        f"{'m_prop':>8} "
        f"{'P0':>8} "
        f"{'Kn':>7} "
        f"{'FS':>6} "
        f"{'status':>8}"
    )
    print(cab)
    print("  " + "-" * (len(cab) - 2))

    linhas = []
    for chave, spec in variacoes.items():
        d = derivar_motor(spec)
        fs = d.diagnosticos[0].valor if d.diagnosticos else float("nan")
        ok_geral = all(x.ok for x in d.diagnosticos) if d.diagnosticos else True
        status = "✓ OK" if ok_geral else "✗ ALERTA"
        p0_str = f"{d.p0_pico / 1e6:>7.3f}M" if d.p0_pico is not None else "     —  "
        kn_str = f"{d.kn_pico:>7.1f}" if d.kn_pico is not None else "      —"

        print(
            f"  {chave:<20} "
            f"{d.total_impulse:>10.2f} "
            f"{d.propellant_mass:>7.3f}k "
            f"{p0_str} "
            f"{kn_str} "
            f"{fs:>6.3f} "
            f"{status:>8}"
        )
        linhas.append((chave, d, ok_geral))

    falhas = [(c, d) for c, d, ok in linhas if not ok]
    if falhas:
        _sub("Detalhes dos alertas")
        for chave, d in falhas:
            print(f"  [{chave}]")
            for diag in d.diagnosticos:
                if not diag.ok:
                    print(f"    {diag.linha()}")


def relatorio_estrutura(foguete: FogueteSpec) -> None:
    """Imprime o detalhamento estrutural (comparando modo calculado e modo medido)."""
    _titulo(f"ESTRUTURA — {foguete.nome.upper()}")
    _linha("raio externo", _fmt(foguete.raio * 1000, 1, "mm"))

    if foguete.componentes and foguete.aleta is not None and foguete.coifa is not None:
        r = resolver(
            componentes=foguete.componentes,
            spec_aleta=foguete.aleta,
            spec_coifa=foguete.coifa,
            raio=foguete.raio,
        )
        _sub("Modo Calculado (analítico por componentes)")
        _linha("massa seca", _fmt(r.massa_seca, 4, "kg"))
        _linha("CG sem motor", _fmt(r.cg_sem_motor, 4, "m"))
        _linha("I_11 = I_22 (pitch/yaw)", _fmt(r.inercia_transversal, 6, "kg·m²"))
        _linha("I_33 (roll)", _fmt(r.inercia_longitudinal, 6, "kg·m²"))
    else:
        r = None

    if foguete.geometria_medida is not None:
        gm = foguete.geometria_medida
        _sub("Modo Medido (bancada / OpenRocket)")
        _linha("massa seca", _fmt(gm.massa_seca, 4, "kg"))
        _linha("CG sem motor", _fmt(gm.cg_sem_motor, 4, "m"))
        _linha("I_11 = I_22 (pitch/yaw)", _fmt(gm.inercia_transversal, 6, "kg·m²"))
        _linha("I_33 (roll)", _fmt(gm.inercia_longitudinal, 6, "kg·m²"))

    if r is not None and foguete.coifa is not None and foguete.aleta is not None:
        comp_modulos = sum(
            c.comprimento for c in foguete.componentes if c.nome.startswith("Módulo")
        )
        fim_corpo = foguete.coifa.length + comp_modulos
        comp_total = max(fim_corpo, foguete.motor_position)

        _sub("Comprimentos")
        _linha("coifa", _fmt(foguete.coifa.length, 4, "m"))
        _linha("corpo (módulos)", _fmt(comp_modulos, 4, "m"))
        _linha("fim do corpo", _fmt(fim_corpo, 4, "m"))
        _linha("posição do motor (tubeira)", _fmt(foguete.motor_position, 4, "m"))
        _linha("COMPRIMENTO TOTAL", _fmt(comp_total, 4, "m"))

        _titulo("COMPONENTES (nariz → cauda)")
        print(
            f"  {'#':>2}  {'nome':<30} {'massa':>8} {'pos':>7} "
            f"{'L':>7} {'r_e':>7} {'r_i':>7}"
        )
        print(
            f"  {'-'*2}  {'-'*30} {'-'*8} {'-'*7} "
            f"{'-'*7} {'-'*7} {'-'*7}"
        )

        for i, (spec, deriv) in enumerate(zip(foguete.componentes, r.componentes)):
            if isinstance(spec, TuboSpec):
                re = spec.raio_externo * 1000
                ri = spec.raio_interno * 1000
                L = spec.comprimento
                print(
                    f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                    f"{spec.posicao:>7.4f} {L:>7.4f} {re:>7.1f} {ri:>7.1f}"
                )
            else:
                print(
                    f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                    f"{spec.posicao:>7.4f} {'—':>7} {'—':>7} {'—':>7}"
                )

        aleta_spec = foguete.aleta
        a = r.aleta
        _titulo("ALETAS")
        _linha("quantidade", aleta_spec.n)
        _linha("root_chord", _fmt(aleta_spec.root_chord, 4, "m"))
        _linha("tip_chord", _fmt(aleta_spec.tip_chord, 4, "m"))
        _linha("span_le", _fmt(aleta_spec.span_le, 4, "m"))
        _linha("span_te", _fmt(aleta_spec.span_te, 4, "m"))
        _linha("sweep_length", _fmt(aleta_spec.sweep_length, 4, "m"))
        _linha("espessura", _fmt(aleta_spec.thickness, 4, "m"))
        _linha("posição", _fmt(aleta_spec.position, 4, "m"))
        _linha("cant_angle", _fmt(aleta_spec.cant_angle, 2, "°"))

        _sub("Derivadas")
        _linha("área unitária", _fmt(a.area_planform, 6, "m²"))
        _linha("massa unitária", _fmt(a.massa_unitaria, 4, "kg"))
        _linha("massa total", _fmt(a.massa_total, 4, "kg"))
        _linha("CG axial", _fmt(a.X_cg_absoluto, 4, "m"))
        _linha("r_cg", _fmt(a.r_cg, 4, "m"))
        _linha("I_33 roll (todas)", _fmt(a.I_xx, 6, "kg·m²"))
        _linha("I_11/I_22 pitch local", _fmt(a.I_yy_local, 6, "kg·m²"))

        coifa_spec = foguete.coifa
        cf = r.coifa
        _titulo("COIFA")
        _linha("kind", coifa_spec.kind)
        _linha("comprimento", _fmt(coifa_spec.length, 4, "m"))
        _linha("espessura", _fmt(coifa_spec.thickness * 1000, 3, "mm"))
        _linha("ρ casca", _fmt(coifa_spec.densidade, 1, "kg/m³"))
        _linha("massa_extra", _fmt(coifa_spec.massa_extra, 4, "kg"))

        _sub("Derivadas")
        _linha("massa total", _fmt(cf.massa, 4, "kg"))
        _linha("CG", _fmt(cf.cg, 4, "m"))
        _linha("I_33 roll local", _fmt(cf.I_xx_local, 6, "kg·m²"))
        _linha("I_11/I_22 pitch local", _fmt(cf.I_yy_local, 6, "kg·m²"))


def relatorio_seguranca(
    spec: MotorSpec,
    *,
    derivado: MotorDerivado | None = None,
) -> None:
    """Imprime os diagnósticos de segurança do motor."""
    d = derivado if derivado is not None else derivar_motor(spec)

    _titulo("DIAGNÓSTICOS DE SEGURANÇA")
    if not d.diagnosticos:
        print("  (sem diagnósticos — fonte é .eng)")
        return

    for diag in d.diagnosticos:
        print(diag.linha())

    ok = all(x.ok for x in d.diagnosticos)
    print()
    print(f"  RESULTADO: {'✓ Todos passaram' if ok else '✗ Há alertas'}")


def relatorio_voo(
    voo_nominal: Mapping[str, Any],
    voo_estocastico: Mapping[str, Any] | None = None,
    ensemble_estocastico: Mapping[str, Any] | None = None,
    ambiente: Any | None = None,
) -> None:
    """Imprime os parâmetros de lançamento e atmosfera."""
    _titulo("PARÂMETROS DE VOO")

    _sub("Nominal")
    _linha("inclinação", _fmt(voo_nominal.get("inclination"), 1, "°"))
    _linha("heading", _fmt(voo_nominal.get("heading"), 1, "°"))
    _linha("rail_length", _fmt(voo_nominal.get("rail_length"), 2, "m"))

    if voo_estocastico is not None:
        _sub("Estocástico (Monte Carlo)")
        if "rail_length" in voo_estocastico:
            _linha("rail_length σ", _fmt(voo_estocastico["rail_length"] * 1000, 1, "mm"))
        if "inclination" in voo_estocastico:
            _linha("inclinação σ", _fmt(voo_estocastico["inclination"], 2, "°"))
        if "heading" in voo_estocastico:
            _linha("heading σ", _fmt(voo_estocastico["heading"], 2, "°"))
        if ensemble_estocastico and "elevation" in ensemble_estocastico:
            _linha("elevation σ", _fmt(ensemble_estocastico.get("elevation"), 2, "m"))

    if ambiente is not None:
        _sub("Atmosfera (Environment)")
        _linha("data", getattr(ambiente, "date", "—"))
        _linha("latitude", _fmt(getattr(ambiente, "latitude", None), 5, "°"))
        _linha("longitude", _fmt(getattr(ambiente, "longitude", None), 5, "°"))
        _linha("elevação", _fmt(getattr(ambiente, "elevation", None), 1, "m"))
