# src/calculos/seguranca.py
"""Fatores de segurança e verificação de limites operacionais.

Cada função devolve um `DiagnosticoFS` imutável com valor calculado, limite,
status OK/alerta e detalhamento legível. Não importa nada de `configs/`.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.specs import LimitesSeguranca

LIMITES_PADRAO = LimitesSeguranca()


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


def fs_carcaca(
    p0_pico: float,
    case_inner_radius: float,
    case_wall_thickness: float,
    sigma_lim: float | None = None,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    """FS da carcaça cilíndrica de paredes finas (Beer & Johnston).

        σ_circ = P0 · r / t
        FS     = σ_lim / σ_circ
    """
    sigma = sigma_lim if sigma_lim is not None else limites.sigma_lim_carcaca
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


def check_p0(
    p0_pico: float,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="P0 pico",
        valor=p0_pico / 1e6,
        limite_min=None,
        limite_max=limites.p0_max / 1e6,
        unidade="MPa",
        ok=p0_pico <= limites.p0_max,
        detalhe="pressão máxima na câmara",
    )


def check_kn(
    kn_pico: float,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="Kn pico",
        valor=kn_pico,
        limite_min=None,
        limite_max=limites.kn_max,
        unidade="—",
        ok=kn_pico <= limites.kn_max,
        detalhe="razão área queima / garganta",
    )


def check_mass_flux(
    mass_flux_pico: float,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="mass flux pico",
        valor=mass_flux_pico,
        limite_min=None,
        limite_max=limites.mass_flux_max,
        unidade="kg/(m²·s)",
        ok=mass_flux_pico <= limites.mass_flux_max,
        detalhe="2 lb/(in²·s) é o limite típico do KNSB",
    )
