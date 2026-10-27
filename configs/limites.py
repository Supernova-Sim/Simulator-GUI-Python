# configs/limites.py
"""Limites de projeto do foguete (IREC + restrições estruturais/operacionais)."""
from __future__ import annotations

from configs.material import SIGMA_LIM_AL6063_T5
from src.specs import LimitesSeguranca

# ============================================================
#  Fatores de segurança
# ============================================================
FS_MIN_CARCACA = 2.0        # IREC 2027 (era 1.9 no Medusa antigo)
FS_ALVO_CARCACA = 3.0       # Alvo interno — Beer & Johnston no relatório
FS_MIN_ALETAS = 2.0
FS_MIN_ESTRUTURA = 2.0
FS_MIN_RECUPERACAO = 2.0

# ============================================================
#  Limites operacionais do motor
# ============================================================
P0_MAX = 8.0e6              # Pa — do .ric
KN_MAX = 250.0              # — estimativa conservadora
MASS_FLUX_MAX = 1406.0      # kg/(m²·s) — 2 lb/(in²·s), do .ric
PORT_THROAT_MIN = 2.0       # — do .ric
EROSION_MAX_GARGANTA = 0.02 # 2% de erosão da garganta

LIMITES_IREC = LimitesSeguranca(
    fs_min_carcaca=FS_MIN_CARCACA,
    fs_alvo_carcaca=FS_ALVO_CARCACA,
    fs_min_aletas=FS_MIN_ALETAS,
    fs_min_estrutura=FS_MIN_ESTRUTURA,
    fs_min_recuperacao=FS_MIN_RECUPERACAO,
    p0_max=P0_MAX,
    kn_max=KN_MAX,
    mass_flux_max=MASS_FLUX_MAX,
    port_throat_min=PORT_THROAT_MIN,
    erosion_max_garganta=EROSION_MAX_GARGANTA,
    sigma_lim_carcaca=SIGMA_LIM_AL6063_T5,
)
