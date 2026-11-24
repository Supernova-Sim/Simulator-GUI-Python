"""Pure deterministic Flight Safety Envelope calculations (SI units, zero I/O)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from hefesto.domain import (
    FinComponent,
    FinSetSpec,
    FlightResult,
    FlightSafetyCheck,
    FlightSafetyLimits,
    FlightSafetyReport,
    FlightSafetyStatus,
    MotorSpec,
    RocketSpec,
    SafetyCriterion,
    SafetyReport,
)
from hefesto.physics.constants import STANDARD_GRAVITY_M_S2
from hefesto.physics.geometry import hollow_cylinder_volume_m3

DEFAULT_FLIGHT_SAFETY_LIMITS = FlightSafetyLimits()

# NACA TN 4197 / Martin denominator constant: 39.3 / (2 * 14.696) = 1.337098...
_NACA_4197_DENOMINATOR = 1.3371


def _is_pos(value: float | None) -> bool:
    return (
        value is not None
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0.0
    )


def _check(
    key: str,
    category: str,
    name: str,
    status: FlightSafetyStatus,
    *,
    value: float | None = None,
    unit: str = "",
    limit: str = "",
    detail: str = "",
    rec: str = "",
) -> FlightSafetyCheck:
    return FlightSafetyCheck(
        key=key,
        category=category,
        name=name,
        status=status,
        value=value,
        unit=unit,
        reference_limit=limit,
        detail=detail,
        recommendation=rec,
    )


def compute_fin_flutter_velocity_ms(
    *,
    root_chord_m: float,
    tip_chord_m: float,
    span_m: float,
    thickness_m: float,
    shear_modulus_pa: float,
    ambient_pressure_pa: float,
    speed_of_sound_ms: float,
) -> float:
    """Compute fin flutter critical velocity V_f (m/s) via NACA TN 4197 (Martin, strict SI)."""
    for label, val in (
        ("root_chord_m", root_chord_m),
        ("span_m", span_m),
        ("thickness_m", thickness_m),
        ("shear_modulus_pa", shear_modulus_pa),
        ("ambient_pressure_pa", ambient_pressure_pa),
        ("speed_of_sound_ms", speed_of_sound_ms),
    ):
        if not _is_pos(val):
            raise ValueError(f"{label} must be finite and > 0, got {val!r}")
    if isinstance(tip_chord_m, bool) or not math.isfinite(tip_chord_m) or tip_chord_m < 0.0:
        raise ValueError(f"tip_chord_m must be finite and >= 0, got {tip_chord_m!r}")

    fin_area = 0.5 * (root_chord_m + tip_chord_m) * span_m
    ar = (span_m * span_m) / fin_area
    taper = tip_chord_m / root_chord_m
    num = shear_modulus_pa * (ar + 2.0) * ((thickness_m / root_chord_m) ** 3)
    den = _NACA_4197_DENOMINATOR * (ar**3) * (taper + 1.0) * ambient_pressure_pa
    return speed_of_sound_ms * math.sqrt(num / den)


def _derive_fin_params(
    fins: FinSetSpec,
    components: Sequence[FinComponent],
) -> tuple[float | None, float | None, float | None, float | None]:
    root_c, tip_c, span = fins.root_chord_m, fins.tip_chord_m, fins.span_m
    if root_c is None or tip_c is None or span is None:
        pts = fins.shape_points_m
        ys = [y for _, y in pts]
        min_y, max_y = min(ys), max(ys)
        derived_span = max_y - min_y
        tol = max(1e-6, derived_span * 1e-3)
        root_xs = [x for x, y in pts if abs(y - min_y) <= tol]
        tip_xs = [x for x, y in pts if abs(y - max_y) <= tol]
        if root_c is None and len(root_xs) >= 2:
            root_c = max(root_xs) - min(root_xs)
        if tip_c is None and tip_xs:
            tip_c = (max(tip_xs) - min(tip_xs)) if len(tip_xs) >= 2 else 0.0
        if span is None and derived_span > 0.0:
            span = derived_span
    thickness = fins.thickness_m if fins.thickness_m is not None else (
        components[0].thickness_m if components else None
    )
    return root_c, tip_c, span, thickness


def _eval_fin_flutter(
    flight: FlightResult,
    rocket: RocketSpec | None,
    lim: FlightSafetyLimits,
) -> tuple[FlightSafetyCheck, float | None, float | None]:
    cat, name = "Aerodinâmica & Aeroelasticidade", "Fin Flutter (NACA TN 4197)"
    ref = f"SF ≥ {lim.min_flutter_safety_factor_warn:.2f}"
    if rocket is None:
        return _check("fin_flutter", cat, name, FlightSafetyStatus.NOT_EVALUATED, limit=ref,
                      detail="Especificação do foguete indisponível."), None, None

    fin_comps = [c for c in rocket.components if isinstance(c, FinComponent)]
    root_c, tip_c, span, thickness = _derive_fin_params(rocket.fins, fin_comps)
    shear_g = rocket.fins.shear_modulus_pa
    if shear_g is None or thickness is None:
        return _check(
            "fin_flutter", cat, name, FlightSafetyStatus.NOT_EVALUATED, limit=ref,
            detail="Módulo de cisalhamento G ou espessura da aleta não configurados.",
            rec="Informe material/G (GPa) e espessura na página de Configuração.",
        ), None, None

    p_amb, a_sound = flight.max_speed_ambient_pressure_pa, flight.max_speed_sound_speed_ms
    if not (_is_pos(p_amb) and _is_pos(a_sound)):
        return _check(
            "fin_flutter", cat, name, FlightSafetyStatus.NOT_EVALUATED, limit=ref,
            detail="Telemetria atmosférica em V_max indisponível neste snapshot.",
        ), None, None
    assert p_amb is not None and a_sound is not None

    if root_c is None or tip_c is None or span is None or not _is_pos(flight.max_speed_ms):
        return _check("fin_flutter", cat, name, FlightSafetyStatus.NOT_EVALUATED, limit=ref,
                      detail="Geometria da aleta ou V_max insuficiente."), None, None

    vf = compute_fin_flutter_velocity_ms(
        root_chord_m=root_c, tip_chord_m=tip_c, span_m=span, thickness_m=thickness,
        shear_modulus_pa=shear_g, ambient_pressure_pa=p_amb, speed_of_sound_ms=a_sound,
    )
    sf = vf / flight.max_speed_ms
    if sf < lim.min_flutter_safety_factor_fail:
        st, rec = FlightSafetyStatus.FAIL, "Risco crítico de flutter: aumente t ou G."
    elif sf < lim.min_flutter_safety_factor_warn:
        st, rec = FlightSafetyStatus.WARN, "Margem de flutter reduzida (< 1.50)."
    else:
        st, rec = FlightSafetyStatus.PASS, ""
    mat = rocket.fins.material_name or f"G={shear_g / 1e9:.2f} GPa"
    detail = (
        f"V_f={vf:.1f} m/s vs V_max={flight.max_speed_ms:.1f} m/s "
        f"({mat}, P={p_amb / 1e3:.1f} kPa)."
    )
    lim_str = (
        f"≥ {lim.min_flutter_safety_factor_warn:.2f} "
        f"(falha < {lim.min_flutter_safety_factor_fail:.2f})"
    )
    return _check(
        "fin_flutter", cat, name, st, value=sf, unit="x",
        limit=lim_str, detail=detail, rec=rec,
    ), vf, sf


def _eval_stability(flight: FlightResult, lim: FlightSafetyLimits) -> tuple[FlightSafetyCheck, ...]:
    cat = "Estabilidade & Weathercocking"
    margin = (
        flight.out_of_rail_static_margin_calibers
        if flight.out_of_rail_static_margin_calibers is not None
        else flight.min_static_margin_calibers
    )
    src = "saída do trilho" if flight.out_of_rail_static_margin_calibers is not None else "mínima"
    if margin < lim.min_static_margin_fail_calibers:
        sm_st, sm_rec = FlightSafetyStatus.FAIL, "Foguete instável (< 1.0 cal)."
    elif margin < lim.min_static_margin_warn_calibers:
        sm_st, sm_rec = FlightSafetyStatus.WARN, "Estabilidade marginal (< 1.5 cal)."
    elif margin > lim.max_static_margin_warn_calibers:
        sm_st, sm_rec = FlightSafetyStatus.WARN, (
            "Risco de superestabilidade (weathercocking > 3.5 cal): reduza aleta ou ajuste CG."
        )
    else:
        sm_st, sm_rec = FlightSafetyStatus.PASS, ""
    c_sm = _check(
        "static_margin", cat, f"Margem Estática ({src})", sm_st, value=margin, unit="cal",
        limit=(
            f"{lim.min_static_margin_warn_calibers:.1f} – "
            f"{lim.max_static_margin_warn_calibers:.1f} cal"
        ),
        detail=f"Margem na {src}: {margin:.2f} cal (mín={flight.min_static_margin_calibers:.2f}).",
        rec=sm_rec,
    )

    vxy = flight.apogee_horizontal_speed_ms
    if vxy is None:
        c_vxy = _check("apogee_horizontal_speed", cat, "Velocidade Horizontal no Apogeu",
                       FlightSafetyStatus.NOT_EVALUATED,
                       limit=f"≤ {lim.max_apogee_horizontal_speed_warn_ms:.0f} m/s",
                       detail="V_xy no apogeu indisponível neste snapshot.")
    else:
        if vxy > lim.max_apogee_horizontal_speed_fail_ms:
            v_st, v_rec = FlightSafetyStatus.FAIL, "V_xy > 40 m/s no apogeu: weathercocking severo."
        elif vxy > lim.max_apogee_horizontal_speed_warn_ms:
            v_st, v_rec = FlightSafetyStatus.WARN, "V_xy > 25 m/s no apogeu: deriva elevada."
        else:
            v_st, v_rec = FlightSafetyStatus.PASS, ""
        c_vxy = _check(
            "apogee_horizontal_speed", cat, "Velocidade Horizontal no Apogeu", v_st,
            value=vxy, unit="m/s",
            limit=(
                f"≤ {lim.max_apogee_horizontal_speed_warn_ms:.0f} m/s "
                f"(falha > {lim.max_apogee_horizontal_speed_fail_ms:.0f})"
            ),
            detail=f"V_xy no apogeu = {vxy:.1f} m/s.", rec=v_rec,
        )

    tilt = flight.burnout_tilt_deg
    if tilt is None:
        c_tilt = _check("burnout_tilt", cat, "Inclinação no Burnout",
                        FlightSafetyStatus.NOT_EVALUATED,
                        limit=f"≤ {lim.max_burnout_tilt_warn_deg:.0f}°",
                        detail="Inclinação no burnout indisponível neste snapshot.")
    else:
        if tilt > lim.max_burnout_tilt_fail_deg:
            t_st, t_rec = FlightSafetyStatus.FAIL, "Desvio > 40° no burnout: voo raso."
        elif tilt > lim.max_burnout_tilt_warn_deg:
            t_st, t_rec = FlightSafetyStatus.WARN, "Desvio > 25° no burnout."
        else:
            t_st, t_rec = FlightSafetyStatus.PASS, ""
        c_tilt = _check(
            "burnout_tilt", cat, "Inclinação no Burnout", t_st, value=tilt, unit="°",
            limit=(
                f"≤ {lim.max_burnout_tilt_warn_deg:.0f}° "
                f"(falha > {lim.max_burnout_tilt_fail_deg:.0f}°)"
            ),
            detail=f"Desvio vertical no burnout = {tilt:.1f}°.", rec=t_rec,
        )
    return (c_sm, c_vxy, c_tilt)


def _eval_liftoff(
    flight: FlightResult, motor: MotorSpec | None, lim: FlightSafetyLimits,
) -> tuple[tuple[FlightSafetyCheck, ...], float | None, float | None]:
    cat = "Decolagem"
    twr: float | None = None
    if motor is not None:
        dt = motor.burn_time_s[1] - motor.burn_time_s[0]
        prop_mass = sum(
            hollow_cylinder_volume_m3(g.outer_radius_m, g.inner_radius_m, g.length_m)
            for g in motor.grains
        ) * motor.propellant_density_kg_m3
        m0 = flight.dry_mass_kg + prop_mass
        if dt > 0.0 and m0 > 0.0 and flight.total_impulse_ns > 0.0:
            twr = (flight.total_impulse_ns / dt) / (m0 * STANDARD_GRAVITY_M_S2)

    if twr is None:
        c_twr = _check("twr", cat, "Razão Empuxo-Peso (TWR)", FlightSafetyStatus.NOT_EVALUATED,
                       limit=f"≥ {lim.min_twr_warn:.1f}", detail="Dados do motor indisponíveis.")
    else:
        if twr < lim.min_twr_fail:
            st, rec = FlightSafetyStatus.FAIL, "TWR < 4.0: submotorizado para decolagem segura."
        elif twr < lim.min_twr_warn:
            st, rec = FlightSafetyStatus.WARN, "TWR < 5.0: sensível a rajadas de vento."
        else:
            st, rec = FlightSafetyStatus.PASS, ""
        c_twr = _check(
            "twr", cat, "Razão Empuxo-Peso (TWR)", st, value=twr, unit=":1",
            limit=f"≥ {lim.min_twr_warn:.1f} (falha < {lim.min_twr_fail:.1f})",
            detail=f"TWR médio na decolagem = {twr:.2f}.", rec=rec,
        )

    v_rail = flight.rail_exit_velocity_ms
    if v_rail < lim.min_rail_exit_velocity_fail_ms:
        vr_st, vr_rec = FlightSafetyStatus.FAIL, "V_rail < 15 m/s: aumente trilho ou empuxo."
    elif v_rail < lim.min_rail_exit_velocity_warn_ms:
        vr_st, vr_rec = FlightSafetyStatus.WARN, "V_rail < 20 m/s: abaixo da meta ideal."
    else:
        vr_st, vr_rec = FlightSafetyStatus.PASS, ""
    c_vrail = _check(
        "rail_exit_velocity", cat, "Velocidade de Saída do Trilho", vr_st, value=v_rail, unit="m/s",
        limit=(
            f"≥ {lim.min_rail_exit_velocity_warn_ms:.0f} m/s "
            f"(falha < {lim.min_rail_exit_velocity_fail_ms:.0f})"
        ),
        detail=f"V_rail = {v_rail:.1f} m/s.", rec=vr_rec,
    )

    wind = flight.rail_exit_wind_speed_ms
    aoa: float | None = None
    if wind is None or v_rail <= 0.0:
        c_aoa = _check(
            "rail_aoa", cat, "Ângulo de Ataque na Saída do Trilho",
            FlightSafetyStatus.NOT_EVALUATED, limit=f"≤ {lim.max_rail_aoa_pass_deg:.0f}°",
            detail="Vento na saída do trilho indisponível.",
        )
    else:
        aoa = math.degrees(math.atan2(wind, v_rail))
        if aoa > lim.max_rail_aoa_warn_deg:
            a_st, a_rec = FlightSafetyStatus.FAIL, "AoA > 20° na saída do trilho: risco de estol."
        elif aoa > lim.max_rail_aoa_pass_deg:
            a_st, a_rec = FlightSafetyStatus.WARN, "AoA > 12° na saída do trilho."
        else:
            a_st, a_rec = FlightSafetyStatus.PASS, ""
        c_aoa = _check(
            "rail_aoa", cat, "Ângulo de Ataque na Saída do Trilho", a_st, value=aoa, unit="°",
            limit=f"≤ {lim.max_rail_aoa_pass_deg:.0f}° (falha > {lim.max_rail_aoa_warn_deg:.0f}°)",
            detail=f"arctan({wind:.1f}/{v_rail:.1f}) = {aoa:.1f}°.", rec=a_rec,
        )
    return (c_twr, c_vrail, c_aoa), twr, aoa


def _eval_loads(
    flight: FlightResult, motor_safety: SafetyReport | None, lim: FlightSafetyLimits,
) -> tuple[tuple[FlightSafetyCheck, ...], float | None]:
    cat = "Cargas Estruturais"
    max_q = (
        flight.max_dynamic_pressure_pa / 1000.0
        if flight.max_dynamic_pressure_pa is not None
        else None
    )
    c_q = _check(
        "max_q", cat, "Pressão Dinâmica Máxima (Max-Q)",
        FlightSafetyStatus.PASS if max_q is not None else FlightSafetyStatus.NOT_EVALUATED,
        value=max_q, unit="kPa", limit="Informativo",
        detail=f"Max-Q = {max_q:.2f} kPa." if max_q is not None else "Max-Q indisponível.",
    )

    g_max = flight.max_axial_acceleration_g
    if g_max is None:
        c_g = _check("g_max", cat, "Aceleração Máxima (G_max)", FlightSafetyStatus.NOT_EVALUATED,
                     limit=f"≤ {lim.max_axial_accel_warn_g:.0f} G", detail="G_max indisponível.")
    else:
        if g_max > lim.max_axial_accel_fail_g:
            g_st, g_rec = FlightSafetyStatus.FAIL, "Aceleração > 25 G: risco estrutural."
        elif g_max > lim.max_axial_accel_warn_g:
            g_st, g_rec = FlightSafetyStatus.WARN, "Aceleração > 15 G: verifique aviônica."
        else:
            g_st, g_rec = FlightSafetyStatus.PASS, ""
        c_g = _check(
            "g_max", cat, "Aceleração Máxima (G_max)", g_st, value=g_max, unit="G",
            limit=(
                f"≤ {lim.max_axial_accel_warn_g:.0f} G "
                f"(falha > {lim.max_axial_accel_fail_g:.0f} G)"
            ),
            detail=f"Pico de aceleração = {g_max:.1f} G.", rec=g_rec,
        )

    case_chk = next(
        (c for c in motor_safety.checks if c.criterion == SafetyCriterion.CASE_SAFETY_FACTOR),
        None,
    ) if motor_safety is not None else None
    if case_chk is None or case_chk.value is None:
        c_fs = _check("case_safety_factor", cat, "Fator de Segurança da Carcaça",
                      FlightSafetyStatus.NOT_EVALUATED, limit="≥ 2.00 (meta 3.00)",
                      detail="FS da carcaça indisponível.")
    else:
        target = motor_safety.limits.target_case_safety_factor if motor_safety else 3.0
        if not case_chk.passed:
            fs_st, fs_rec = FlightSafetyStatus.FAIL, "FS da carcaça abaixo do mínimo."
        elif case_chk.value < target:
            fs_st, fs_rec = FlightSafetyStatus.WARN, f"FS abaixo da meta ({target:.2f})."
        else:
            fs_st, fs_rec = FlightSafetyStatus.PASS, ""
        c_fs = _check(
            "case_safety_factor", cat, "Fator de Segurança da Carcaça", fs_st,
            value=case_chk.value, unit="x",
            limit=f"≥ {case_chk.min_limit or 2.0:.2f} (meta ≥ {target:.2f})",
            detail=case_chk.detail, rec=fs_rec,
        )
    return (c_q, c_g, c_fs), max_q


def _eval_recovery(
    flight: FlightResult, lim: FlightSafetyLimits,
) -> tuple[tuple[FlightSafetyCheck, ...], float | None, float | None]:
    cat = "Recuperação"
    max_n: float | None = None
    max_g: float | None = None
    if not flight.parachute_deploy_events:
        c_shock = _check(
            "parachute_opening_shock", cat, "Opening Shock dos Paraquedas",
            FlightSafetyStatus.NOT_EVALUATED, limit=f"≤ {lim.max_parachute_shock_warn_g:.0f} G",
            detail="Nenhum disparo de paraquedas registrado.",
        )
    else:
        w_burn = flight.dry_mass_kg * STANDARD_GRAVITY_M_S2
        cx = lim.parachute_opening_factor_cx
        worst = FlightSafetyStatus.PASS
        parts: list[str] = []
        recs: list[str] = []
        for ev in flight.parachute_deploy_events:
            f_n = 0.5 * ev.deploy_air_density_kg_m3 * (ev.deploy_speed_ms**2) * ev.cd_s * cx
            g_v = f_n / w_burn
            max_n = f_n if max_n is None or f_n > max_n else max_n
            max_g = g_v if max_g is None or g_v > max_g else max_g
            parts.append(f"{ev.name}: {f_n:.0f} N ({g_v:.1f} G) @ {ev.deploy_speed_ms:.1f} m/s")
            if (
                g_v > lim.max_parachute_shock_fail_g
                or ev.deploy_speed_ms > lim.max_parachute_deploy_speed_fail_ms
            ):
                worst = FlightSafetyStatus.FAIL
                recs.append(f"{ev.name}: choque/velocidade críticos.")
            elif (
                g_v > lim.max_parachute_shock_warn_g
                or ev.deploy_speed_ms > lim.max_parachute_deploy_speed_warn_ms
            ) and worst != FlightSafetyStatus.FAIL:
                worst = FlightSafetyStatus.WARN
                recs.append(f"{ev.name}: velocidade/choque elevados.")
        c_shock = _check(
            "parachute_opening_shock", cat, "Opening Shock dos Paraquedas", worst,
            value=max_g, unit="G", limit=f"≤ {lim.max_parachute_shock_warn_g:.0f} G (C_x={cx:.1f})",
            detail=" | ".join(parts), rec=" ".join(recs),
        )

    imp_v = (
        flight.total_impact_speed_ms
        if flight.total_impact_speed_ms is not None
        else flight.landing_velocity_ms
    )
    if imp_v is None:
        c_imp = _check("impact_speed", cat, "Velocidade Total de Impacto",
                       FlightSafetyStatus.NOT_EVALUATED,
                       limit=f"≤ {lim.max_impact_speed_pass_ms:.1f} m/s",
                       detail="Velocidade de impacto indisponível.")
    else:
        if imp_v > lim.max_impact_speed_warn_ms:
            i_st, i_rec = FlightSafetyStatus.FAIL, "Pouso > 10 m/s: aumente Cd*S do principal."
        elif imp_v > lim.max_impact_speed_pass_ms:
            i_st, i_rec = FlightSafetyStatus.WARN, "Pouso entre 7.5 e 10 m/s."
        else:
            i_st, i_rec = FlightSafetyStatus.PASS, ""
        c_imp = _check(
            "impact_speed", cat, "Velocidade Total de Impacto", i_st, value=imp_v, unit="m/s",
            limit=(
                f"≤ {lim.max_impact_speed_pass_ms:.1f} m/s "
                f"(falha > {lim.max_impact_speed_warn_ms:.1f})"
            ),
            detail=f"Velocidade total no impacto = {imp_v:.2f} m/s.", rec=i_rec,
        )
    return (c_shock, c_imp), max_n, max_g


def evaluate_flight_safety(
    flight: FlightResult,
    *,
    rocket: RocketSpec | None = None,
    motor: MotorSpec | None = None,
    motor_safety: SafetyReport | None = None,
    limits: FlightSafetyLimits | None = None,
) -> FlightSafetyReport:
    """Evaluate all Flight Safety Envelope criteria from FlightResult and optional specs."""
    lim = DEFAULT_FLIGHT_SAFETY_LIMITS if limits is None else limits
    res_motor = motor if motor is not None else (rocket.motor if rocket is not None else None)
    flutter_chk, vf, sf = _eval_fin_flutter(flight, rocket, lim)
    stab_chks = _eval_stability(flight, lim)
    life_chks, twr, aoa = _eval_liftoff(flight, res_motor, lim)
    load_chks, max_q = _eval_loads(flight, motor_safety, lim)
    rec_chks, shock_n, shock_g = _eval_recovery(flight, lim)

    checks = (flutter_chk, *stab_chks, *life_chks, *load_chks, *rec_chks)
    statuses = {c.status for c in checks}
    if FlightSafetyStatus.FAIL in statuses:
        overall = FlightSafetyStatus.FAIL
    elif FlightSafetyStatus.WARN in statuses:
        overall = FlightSafetyStatus.WARN
    elif FlightSafetyStatus.PASS in statuses:
        overall = FlightSafetyStatus.PASS
    else:
        overall = FlightSafetyStatus.NOT_EVALUATED

    return FlightSafetyReport(
        limits=lim,
        checks=checks,
        overall_status=overall,
        fin_flutter_velocity_ms=vf,
        fin_flutter_safety_factor=sf,
        max_q_kpa=max_q,
        twr=twr,
        rail_aoa_deg=aoa,
        max_parachute_shock_n=shock_n,
        max_parachute_shock_g=shock_g,
    )


__all__ = [
    "DEFAULT_FLIGHT_SAFETY_LIMITS",
    "compute_fin_flutter_velocity_ms",
    "evaluate_flight_safety",
]
