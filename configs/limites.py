# configs/limites.py
"""Limites de projeto do foguete.

Centraliza os critérios de aceitação da IREC + restrições estruturais.
Qualquer valor aqui é um *limite* — o código compara e dispara alerta.

Referências:
- IREC 2027 Spaceport America Cup — FS mínimo estrutural = 2.0
- Relatório Medusa: alumínio 6063-T5 σ_lim = 145 MPa
- OpenMotor .ric: maxPressure=8 MPa, maxMassFlux=1406 kg/(m²·s), minPortThroat=2.0
"""



# ============================================================
#  Fatores de segurança
# ============================================================
FS_MIN_CARCACA        = 2.0     # IREC 2027 (era 1.9 no Medusa antigo)
FS_ALVO_CARCACA       = 3.0     # Alvo interno — Beer & Johnston no relatório
FS_MIN_ALETAS         = 2.0
FS_MIN_ESTRUTURA      = 2.0
FS_MIN_RECUPERACAO    = 2.0


# ============================================================
#  Limites operacionais do motor
# ============================================================
P0_MAX                = 8.0e6   # Pa — do .ric
KN_MAX                = 250.0   # — estimativa conservadora (OpenMotor já aceita 232)
MASS_FLUX_MAX         = 1406.0  # kg/(m²·s) — 2 lb/(in²·s), do .ric
PORT_THROAT_MIN       = 2.0     # — do .ric
EROSION_MAX_GARGANTA  = 0.02    # 2% de erosão da garganta é o aceitável