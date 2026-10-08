# src/calculos/seguranca.py
"""Fatores de segurança e verificação de limites.

Cada função devolve um `DiagnosticoFS` com valor, limite, OK/não-OK e
mensagem legível. Nada aqui lança exceção por falha de projeto —
o diagnóstico é dado, a decisão é do usuário.
"""
from __future__ import annotations
from dataclasses import dataclass

from configs import limites


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
        return f"  [{marca}] {self.nome:<24} {self.valor:>10.4f} {self.unidade:<12} {cmp}   {self.detalhe}"


# ============================================================
#  Motor — carcaça
# ============================================================
def fs_carcaca(
    p0_pico: float,
    case_inner_radius: float,
    case_wall_thickness: float,
    sigma_lim: float,
) -> DiagnosticoFS:
    """FS da carcaça cilíndrica de paredes finas (Beer & Johnston).

        σ_circ = P0 · r / t
        FS     = σ_lim / σ_circ = σ_lim · t / (P0 · r)
    """
    sigma_circ = p0_pico * case_inner_radius / case_wall_thickness
    fs = sigma_lim / sigma_circ if sigma_circ > 0 else float("inf")
    return DiagnosticoFS(
        nome="FS carcaça",
        valor=fs,
        limite_min=limites.FS_MIN_CARCACA,
        limite_max=None,
        unidade="—",
        ok=fs >= limites.FS_MIN_CARCACA,
        detalhe=f"σ_circ = {sigma_circ / 1e6:.2f} MPa (σ_lim = {sigma_lim / 1e6:.0f} MPa)",
    )


# ============================================================
#  Motor — limites operacionais
# ============================================================
def check_p0(p0_pico: float) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="P0 pico",
        valor=p0_pico / 1e6,
        limite_min=None,
        limite_max=limites.P0_MAX / 1e6,
        unidade="MPa",
        ok=p0_pico <= limites.P0_MAX,
        detalhe="pressão máxima na câmara",
    )


def check_kn(kn_pico: float) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="Kn pico",
        valor=kn_pico,
        limite_min=None,
        limite_max=limites.KN_MAX,
        unidade="—",
        ok=kn_pico <= limites.KN_MAX,
        detalhe="razão área queima / garganta",
    )


def check_mass_flux(mass_flux_pico: float) -> DiagnosticoFS:
    return DiagnosticoFS(
        nome="mass flux pico",
        valor=mass_flux_pico,
        limite_min=None,
        limite_max=limites.MASS_FLUX_MAX,
        unidade="kg/(m²·s)",
        ok=mass_flux_pico <= limites.MASS_FLUX_MAX,
        detalhe="2 lb/(in²·s) é o limite típico do KNSB",
    )

def main() -> None:
    """Smoke test com valores conhecidos do Medusa."""
    # Referência: relatório do Medusa + cálculo manual
    #   P0 = 2.912 MPa, r = 0.05395 m, t = 0.003175 m, σ_lim = 145 MPa
    #   FS esperado = 2.93
    from configs import SIGMA_LIM_AL6063_T5

    diags = [
        fs_carcaca(2.9122e6, 0.05395, 0.003175, SIGMA_LIM_AL6063_T5),
        check_p0(2.9122e6),
        check_kn(232.7390),
        check_mass_flux(1249.4661),
    ]

    for d in diags:
        print(d.linha())

    # Validações
    assert abs(diags[0].valor - 2.93) < 0.01, f"FS esperado 2.93, obtido {diags[0].valor}"
    assert all(d.ok for d in diags), "Algum check falhou"
    print("\n✓ seguranca OK")


if __name__ == "__main__":
    main()