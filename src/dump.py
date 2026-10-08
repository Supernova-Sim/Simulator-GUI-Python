# src/dump.py
"""Imprime toda a configuração do foguete/voo de forma legível.

Uso:
    from src.dump import dump_tudo
    print(dump_tudo())

Ou pela CLI:
    python centralControle/rodar.py dump
"""
from __future__ import annotations

from src.calculos.motor import derivar_motor
from src.modelo import resolver


def _cabecalho(titulo: str) -> str:
    return f"\n{'━' * 68}\n  {titulo}\n{'━' * 68}"


def dump_spec_motor(spec) -> str:
    linhas = [_cabecalho("MOTOR — SPEC (.ric)")]
    linhas.append(f"  nome:            {spec.nome}")
    linhas.append(f"  fonte:           {'ric' if spec.ric_path else 'eng'}")
    linhas.append(f"  ric_path:        {spec.ric_path}")
    linhas.append(f"  thrust_curve:    {spec.thrust_curve_path}")
    linhas.append("")
    linhas.append(f"  nº grãos:        {len(spec.grains)}")
    for i, g in enumerate(spec.grains):
        linhas.append(
            f"    [{i}] L={g.length:.4f} m  r_o={g.outer_radius:.5f}  r_i={g.inner_radius:.5f}"
        )
    linhas.append(f"  separação:       {spec.grain_separation*1000:.1f} mm")
    linhas.append(f"  densidade prop:  {spec.propellant_density:.1f} kg/m³")
    linhas.append("")
    linhas.append(f"  carcaça r_i:     {spec.case_inner_radius*1000:.2f} mm")
    linhas.append(f"  parede t:        {spec.case_wall_thickness*1000:.3f} mm")
    linhas.append(f"  densidade:       {spec.case_density:.1f} kg/m³")
    linhas.append(f"  case_length:     {spec.case_length:.4f} m")
    linhas.append(f"  dry_mass:        {spec.dry_mass:.4f} kg")
    linhas.append("")
    linhas.append(f"  nozzle position: {spec.nozzle_position*1000:.1f} mm")
    linhas.append(f"  nozzle r_exit:   {spec.nozzle_exit_radius*1000:.2f} mm")
    linhas.append(f"  throat r:        {spec.throat_radius*1000:.2f} mm")
    return "\n".join(linhas)


def dump_derivado_motor(d) -> str:
    linhas = [_cabecalho("MOTOR — DERIVADO")]
    linhas.append(f"  burn_time:       {d.burn_time[0]:.3f} → {d.burn_time[1]:.3f} s")
    linhas.append(f"  impulse:         {d.total_impulse:.1f} N·s")
    linhas.append(f"  thrust máx:      {d.max_thrust:.1f} N")
    linhas.append(f"  thrust médio:    {d.total_impulse / (d.burn_time[1] - d.burn_time[0]):.1f} N")
    linhas.append(f"  ISP entregue:    {d.isp_entregue:.2f} s")
    linhas.append("")
    linhas.append(f"  prop mass:       {d.propellant_mass:.4f} kg")
    linhas.append(f"  prop length:     {d.propellant_length:.4f} m")
    linhas.append(f"  stack length:    {d.stack_length:.4f} m")
    linhas.append(f"  CG prop:         {d.cg_propellant:.4f} m")
    linhas.append(f"  r_i efetivo:     {d.grain_inner_radius_effective*1000:.3f} mm")
    linhas.append("")
    linhas.append(f"  dry_mass:        {d.dry_mass:.4f} kg")
    linhas.append(f"  mass_loaded:     {d.mass_loaded:.4f} kg")
    linhas.append(f"  I_xx (roll):     {d.dry_inertia[2]:.6f} kg·m²")
    linhas.append(f"  I_yy (pitch):    {d.dry_inertia[0]:.6f} kg·m²")
    linhas.append("")
    linhas.append("  Balística interna:")
    linhas.append(f"    P0 pico:       {d.p0_pico/1e6:.3f} MPa")
    linhas.append(f"    Kn pico:       {d.kn_pico:.1f}")
    linhas.append(f"    mass flux:     {d.mass_flux_pico:.3f} kg/(m²·s)")
    return "\n".join(linhas)


def dump_diagnosticos(d) -> str:
    linhas = [_cabecalho("DIAGNÓSTICOS DE SEGURANÇA")]
    if not d.diagnosticos:
        linhas.append("  (sem diagnósticos — fonte é .eng)")
        return "\n".join(linhas)
    for diag in d.diagnosticos:
        linhas.append(diag.linha())
    ok = all(x.ok for x in d.diagnosticos)
    linhas.append("")
    linhas.append(f"  RESULTADO: {'✅ Todos passaram' if ok else '❌ Há alertas'}")
    return "\n".join(linhas)


def dump_foguete() -> str:
    from configs import COMPONENTES, ALETA_IREC, COIFA_IREC, FOGUETE

    r = resolver(
        componentes=COMPONENTES,
        spec_aleta=ALETA_IREC,
        spec_coifa=COIFA_IREC,
        raio=FOGUETE["radius"],
    )

    linhas = [_cabecalho("FOGUETE — AGREGADO")]
    linhas.append(f"  raio externo:    {r.raio*1000:.1f} mm")
    linhas.append(f"  massa seca:      {r.massa_seca:.4f} kg")
    linhas.append(f"  CG sem motor:    {r.cg_sem_motor:.4f} m")
    linhas.append(f"  I_xx (roll):     {r.inercia_longitudinal:.6f} kg·m²")
    linhas.append(f"  I_yy (pitch):    {r.inercia_transversal:.6f} kg·m²")

    linhas.append(_cabecalho("COMPONENTES"))
    linhas.append(f"  {'nome':<32} {'massa':>8} {'pos':>8}")
    linhas.append(f"  {'-'*32} {'-'*8} {'-'*8}")
    for c in r.componentes:
        linhas.append(f"  {c.nome:<32} {c.massa:>7.3f}  {c.posicao:>7.4f}")

    linhas.append(_cabecalho("ALETAS"))
    a = r.aleta
    linhas.append(f"  quantidade:      {r.spec_aleta.n}")
    linhas.append(f"  área unitária:   {a.area_planform:.6f} m²")
    linhas.append(f"  massa unitária:  {a.massa_unitaria:.4f} kg")
    linhas.append(f"  massa total:     {a.massa_total:.4f} kg")
    linhas.append(f"  CG axial:        {a.X_cg_absoluto:.4f} m")

    linhas.append(_cabecalho("COIFA"))
    cf = r.coifa
    linhas.append(f"  kind:            {r.spec_coifa.kind}")
    linhas.append(f"  comprimento:     {r.spec_coifa.length:.4f} m")
    linhas.append(f"  massa:           {cf.massa:.4f} kg")
    linhas.append(f"  CG:              {cf.cg:.4f} m")

    return "\n".join(linhas)


def dump_tudo() -> str:
    from configs import MOTOR_IREC

    partes = [
        dump_foguete(),
        dump_spec_motor(MOTOR_IREC),
    ]

    d = derivar_motor(MOTOR_IREC)
    partes.append(dump_derivado_motor(d))
    partes.append(dump_diagnosticos(d))

    return "\n".join(partes) + "\n"


def main() -> None:
    print(dump_tudo())


if __name__ == "__main__":
    main()