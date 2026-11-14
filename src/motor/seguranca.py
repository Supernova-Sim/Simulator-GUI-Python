# src/motor/seguranca.py
"""Fatores de segurança e verificação de limites operacionais.

Cada função devolve um `DiagnosticoFS` imutável com valor calculado, limite,
status OK/alerta e detalhamento legível. Não importa nada de `configs/`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.especificacoes import LIMITES_PADRAO, LimitesSeguranca


@dataclass(frozen=True)
class DiagnosticoFS:
    nome: str
    valor: float
    limite_min: float | None
    limite_max: float | None
    unidade: str
    ok: bool
    detalhe: str

    def linha(self) -> str:
        marca = "OK " if self.ok else "!! "
        if self.limite_min is not None:
            cmp = f">= {self.limite_min:.3f}"
        elif self.limite_max is not None:
            cmp = f"<= {self.limite_max:.3f}"
        else:
            cmp = ""
        return (
            f"  [{marca}] {self.nome:<24} {self.valor:>10.4f} "
            f"{self.unidade:<12} {cmp}   {self.detalhe}"
        )


def _verificar_teto(
    nome: str,
    valor_bruto: float | None,
    limite_max: float,
    unidade: str,
    detalhe: str,
    escala: float = 1.0,
) -> DiagnosticoFS:
    """Verifica um critério de teto (`valor <= limite_max`) em modo fail-closed."""
    if valor_bruto is None or not math.isfinite(valor_bruto):
        return DiagnosticoFS(
            nome=nome,
            valor=float("nan"),
            limite_min=None,
            limite_max=limite_max / escala,
            unidade=unidade,
            ok=False,
            detalhe="dados de entrada inválidos (None ou nan)",
        )
    return DiagnosticoFS(
        nome=nome,
        valor=valor_bruto / escala,
        limite_min=None,
        limite_max=limite_max / escala,
        unidade=unidade,
        ok=valor_bruto <= limite_max,
        detalhe=detalhe,
    )


def fs_carcaca(
    p0_pico: float,
    case_inner_radius: float,
    case_wall_thickness: float,
    sigma_lim: float | None = None,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    """FS da carcaça cilíndrica de paredes finas (Beer & Johnston: σ_circ = P0 · r / t)."""
    sigma = sigma_lim if sigma_lim is not None else limites.sigma_lim_carcaca
    entradas = (p0_pico, case_inner_radius, case_wall_thickness, sigma)
    if any(v is None or not math.isfinite(v) or v <= 0 for v in entradas):
        return DiagnosticoFS(
            nome="FS carcaça",
            valor=float("nan"),
            limite_min=limites.fs_min_carcaca,
            limite_max=None,
            unidade="—",
            ok=False,
            detalhe="dados de entrada inválidos (não positivos ou nan)",
        )

    sigma_circ = p0_pico * case_inner_radius / case_wall_thickness
    fs = sigma / sigma_circ if sigma_circ > 0 else float("inf")
    return DiagnosticoFS(
        nome="FS carcaça",
        valor=fs,
        limite_min=limites.fs_min_carcaca,
        limite_max=None,
        unidade="—",
        ok=fs >= limites.fs_min_carcaca,
        detalhe=f"σ_circ = {sigma_circ / 1e6:.2f} MPa (σ_lim = {sigma / 1e6:.0f} MPa)",
    )


def check_p0(p0_pico: float | None, *, limites: LimitesSeguranca = LIMITES_PADRAO) -> DiagnosticoFS:
    return _verificar_teto("P0 pico", p0_pico, limites.p0_max, "MPa", "pressão máxima na câmara", escala=1e6)


def check_kn(kn_pico: float | None, *, limites: LimitesSeguranca = LIMITES_PADRAO) -> DiagnosticoFS:
    return _verificar_teto("Kn pico", kn_pico, limites.kn_max, "—", "razão área queima / garganta")


def check_mass_flux(
    mass_flux_pico: float | None,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    return _verificar_teto(
        "mass flux pico",
        mass_flux_pico,
        limites.mass_flux_max,
        "kg/(m²·s)",
        "2 lb/(in²·s) é o limite típico do KNSB",
    )
