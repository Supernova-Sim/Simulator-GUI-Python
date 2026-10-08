# hefesto/motorlib_wrapper.py
"""Wrapper do motorlib (OpenMotor) — roda simulação a partir de .ric.

Encapsula a API do OpenMotor para expor uma interface limpa:
    resultado = simular_ric("caminho/Motor.ric")
    print(resultado.resumo())
    curva = resultado.curva_empuxo  # [(t, F), ...]

Nota sobre os canais:
    Alguns canais do motorlib são 2D — [instante][grão]. São:
        mass, massFlow, massFlux, regression, web, machNumber
    Os demais são 1D — [instante]. O dataclass reflete essa separação.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning)
logging.getLogger("uilib").setLevel(logging.ERROR)

from uilib.fileIO import loadFile, fileTypes   # noqa: E402
from motorlib.motor import Motor                # noqa: E402


# ======================================================================
# Helpers
# ======================================================================
def _as_1d(x) -> list[float]:
    """Converte para lista de floats (assume 1D)."""
    return [float(v) for v in x]


def _as_2d(x) -> list[list[float]]:
    """Garante lista de listas de floats."""
    if len(x) and isinstance(x[0], (list, tuple)):
        return [[float(v) for v in sub] for sub in x]
    return [[float(v)] for v in x]


def _pico_2d(x: list[list[float]]) -> float:
    """Máximo varrendo 2 níveis."""
    return max(max(sub) for sub in x) if x else 0.0


def _integrar_trapezio(x: list[float], y: list[float]) -> float:
    total = 0.0
    for i in range(1, len(x)):
        total += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1])
    return total


# ======================================================================
# Saída
# ======================================================================
@dataclass
class MotorResultado:
    """Resultado da simulação de um motor do OpenMotor."""
    success: bool
    alerts: list
    nome: str
    burn_time: float                # s

    # ---------- Séries 1D ----------
    tempo: list[float]              # s
    empuxo: list[float]             # N
    pressao: list[float]            # Pa — câmara
    pressao_saida: list[float]      # Pa — saída da tubeira
    kn: list[float]                 # razão Ab/At
    volume_loading: list[float]     # %
    d_throat: list[float]           # m — erosão da garganta

    # ---------- Séries 2D (tempo × grão) ----------
    massa_por_grao: list[list[float]]       # kg
    mass_flow_por_grao: list[list[float]]   # kg/s
    mass_flux_por_grao: list[list[float]]   # kg/(m²·s)
    regression_por_grao: list[list[float]]  # m
    web_por_grao: list[list[float]]         # m
    mach_por_grao: list[list[float]]        # —

    # ---------- Escalares ----------
    p0_pico: float                  # Pa
    kn_pico: float
    mass_flux_pico: float           # kg/(m²·s) — pior caso entre todos os grãos
    empuxo_max: float               # N
    empuxo_medio: float             # N
    impulso_total: float            # N·s
    isp_entregue: float             # s
    massa_propelente_inicial: float # kg — soma de todos os grãos em t=0
    massa_propelente_final: float   # kg — soma de todos os grãos em t=final
    n_graos: int

    @property
    def curva_empuxo(self) -> list[tuple[float, float]]:
        """[(t, F), ...] em s e N — pronta para o RocketPy."""
        return list(zip(self.tempo, self.empuxo))

    def resumo(self) -> str:
        return "\n".join([
            f"Motor: {self.nome}",
            f"  success:             {self.success}",
            f"  alerts:              {len(self.alerts)}",
            f"  n_graos:             {self.n_graos}",
            f"  burn_time:           {self.burn_time:.3f} s",
            f"  impulse_total:       {self.impulso_total:.1f} N·s",
            f"  thrust_max:          {self.empuxo_max:.1f} N",
            f"  thrust_avg:          {self.empuxo_medio:.1f} N",
            f"  ISP_entregue:        {self.isp_entregue:.2f} s",
            f"  P0_pico:             {self.p0_pico / 1e6:.3f} MPa",
            f"  Kn_pico:             {self.kn_pico:.1f}",
            f"  mass_flux_pico:      {self.mass_flux_pico:.3f} kg/(m²·s)",
            f"  propellant_inicial:  {self.massa_propelente_inicial:.4f} kg",
            f"  propellant_final:    {self.massa_propelente_final:.4f} kg",
        ])


# ======================================================================
# API
# ======================================================================
def simular_ric(ric_path: str | Path) -> MotorResultado:
    """Carrega um .ric, roda o solver do OpenMotor, devolve resultado."""
    ric_path = Path(ric_path)
    if not ric_path.exists():
        raise FileNotFoundError(f".ric não encontrado: {ric_path}")

    props = loadFile(str(ric_path), fileTypes.MOTOR)
    motor = Motor(props)
    sim = motor.runSimulation()

    if not sim.success:
        raise RuntimeError(
            f"Simulação falhou. Alerts: "
            f"{[getattr(a, 'message', str(a)) for a in sim.alerts]}"
        )

    ch = sim.channels

    # --- 1D ---
    tempo         = _as_1d(ch["time"].getData())
    empuxo        = _as_1d(ch["force"].getData())
    pressao       = _as_1d(ch["pressure"].getData())
    pressao_saida = _as_1d(ch["exitPressure"].getData())
    kn            = _as_1d(ch["kn"].getData())
    vol_loading   = _as_1d(ch["volumeLoading"].getData())
    d_throat      = _as_1d(ch["dThroat"].getData())

    # --- 2D ---
    massa_por_grao      = _as_2d(ch["mass"].getData())
    mass_flow_por_grao  = _as_2d(ch["massFlow"].getData())
    mass_flux_por_grao  = _as_2d(ch["massFlux"].getData())
    regression_por_grao = _as_2d(ch["regression"].getData())
    web_por_grao        = _as_2d(ch["web"].getData())
    mach_por_grao       = _as_2d(ch["machNumber"].getData())

    # --- Escalares ---
    impulso = _integrar_trapezio(tempo, empuxo)
    burn_time = tempo[-1] - tempo[0] if len(tempo) > 1 else 0.0
    empuxo_medio = impulso / burn_time if burn_time > 0 else 0.0

    # Massa total: soma dos grãos em cada instante
    massa_total_inicial = sum(massa_por_grao[0])
    massa_total_final   = sum(massa_por_grao[-1])

    try:
        nome = sim.getDesignation()
    except Exception:
        nome = "Motor (via .ric)"

    try:
        isp = float(sim.getISP())
    except Exception:
        isp = float("nan")

    return MotorResultado(
        success=sim.success,
        alerts=list(sim.alerts),
        nome=nome,
        burn_time=burn_time,
        tempo=tempo,
        empuxo=empuxo,
        pressao=pressao,
        pressao_saida=pressao_saida,
        kn=kn,
        volume_loading=vol_loading,
        d_throat=d_throat,
        massa_por_grao=massa_por_grao,
        mass_flow_por_grao=mass_flow_por_grao,
        mass_flux_por_grao=mass_flux_por_grao,
        regression_por_grao=regression_por_grao,
        web_por_grao=web_por_grao,
        mach_por_grao=mach_por_grao,
        p0_pico=max(pressao),
        kn_pico=max(kn),
        mass_flux_pico=_pico_2d(mass_flux_por_grao),
        empuxo_max=max(empuxo),
        empuxo_medio=empuxo_medio,
        impulso_total=impulso,
        isp_entregue=isp,
        massa_propelente_inicial=massa_total_inicial,
        massa_propelente_final=massa_total_final,
        n_graos=len(massa_por_grao[0]),
    )


# ======================================================================
# CLI rápida
# ======================================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m hefesto.calculos.motorlib_wrapper <arquivo.ric>")
        sys.exit(1)

    r = simular_ric(sys.argv[1])
    print(r.resumo())