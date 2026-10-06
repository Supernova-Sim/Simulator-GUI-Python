# Dados convertidos para SI (kg, metros)
# Legenda: r_e (Raio Externo), r_i (Raio Interno), l (Comprimento), x (Posição CG Global)

componentes = [
    # --- Módulos Externos (Tubos e Coifa) ---
    {"nome": "Coifa", "m": 1.300, "x": 0.2795, "r_e": 0.079, "r_i": 0.076, "l": 0.450},
    {"nome": "Módulo Aviônica", "m": 1.4593, "x": 0.7200, "r_e": 0.079, "r_i": 0.076, "l": 0.540},
    {"nome": "Módulo Payload", "m": 1.2161, "x": 1.2150, "r_e": 0.079, "r_i": 0.076, "l": 0.450},
    {"nome": "Módulo Propulsão", "m": 2.4593, "x": 1.8950, "r_e": 0.079, "r_i": 0.076, "l": 0.910},
    {"nome": "Módulo Aletas", "m": 1.0810, "x": 2.5500, "r_e": 0.079, "r_i": 0.076, "l": 0.400},

    # --- Junções (Couplers - Tubos Ocos Internos) ---
    {"nome": "Junção Aviônica/Payload", "m": 0.7583, "x": 0.9900, "r_e": 0.076, "r_i": 0.073, "l": 0.200},
    {"nome": "Junção Payload/Propulsão", "m": 0.7583, "x": 1.4400, "r_e": 0.076, "r_i": 0.073, "l": 0.200},
    {"nome": "Junção Propulsão/Aletas", "m": 0.7583, "x": 2.3500, "r_e": 0.076, "r_i": 0.073, "l": 0.200},

    # --- Anéis e Fixadores (Anéis Vazados) ---
    {"nome": "Fixador Superior 1", "m": 0.1384, "x": 0.9400, "r_e": 0.073, "r_i": 0.063, "l": 0.012},
    {"nome": "Fixador Inferior 1", "m": 0.1384, "x": 1.0400, "r_e": 0.073, "r_i": 0.063, "l": 0.012},
    {"nome": "Fixador Superior 2", "m": 0.1384, "x": 1.3900, "r_e": 0.073, "r_i": 0.063, "l": 0.012},
    {"nome": "Anel centralizador inf 1", "m": 0.1448, "x": 2.3000, "r_e": 0.073, "r_i": 0.0625, "l": 0.012},
    {"nome": "Anel centralizador sup 1", "m": 0.1448, "x": 2.4000, "r_e": 0.073, "r_i": 0.0625, "l": 0.012},
    {"nome": "Anel centralizador sup 2", "m": 0.3215, "x": 2.6225, "r_e": 0.076, "r_i": 0.057, "l": 0.015},
    {"nome": "Anel centralizador médio 2", "m": 0.3215, "x": 2.6625, "r_e": 0.076, "r_i": 0.057, "l": 0.015},
    {"nome": "Anel centralizador inf 2", "m": 0.3215, "x": 2.7025, "r_e": 0.076, "r_i": 0.057, "l": 0.015},

    # --- Anteparos (Discos Maciços - r_i = 0) ---
    {"nome": "Anteparo Recuperação", "m": 0.5879, "x": 0.6680, "r_e": 0.076, "r_i": 0.000, "l": 0.012},
    {"nome": "Anteparo Inferior", "m": 0.9040, "x": 1.4900, "r_e": 0.073, "r_i": 0.000, "l": 0.020},

    # --- Massas Internas (Cilindros Maciços - r_i = 0) ---
    {"nome": "Paraquedas unreefed", "m": 0.6500, "x": 0.4300, "r_e": 0.070, "r_i": 0.000, "l": 0.300},
    {"nome": "Paraquedas reefed", "m": 0.6500, "x": 0.4300, "r_e": 0.070, "r_i": 0.000, "l": 0.300},
    {"nome": "Sistemas de recuperação", "m": 1.7670, "x": 0.6300, "r_e": 0.030, "r_i": 0.000, "l": 0.060},
    {"nome": "Aviônica", "m": 0.7000, "x": 0.7010, "r_e": 0.050, "r_i": 0.000, "l": 0.050},
    {"nome": "Satélite", "m": 1.4000, "x": 1.2020, "r_e": 0.071, "r_i": 0.000, "l": 0.300},
    {"nome": "Complemento de massa", "m": 2.6000, "x": 1.3680, "r_e": 0.076, "r_i": 0.000, "l": 0.020},

    # --- Componentes Externos (Geometrias Secundárias) ---
    {"nome": "Rail Button (conjunto)", "m": 0.0476, "x": 1.8450, "r_e": 0.020, "r_i": 0.0065, "l": 0.027},
    {"nome": "Aletas (aproximação cilíndrica de varredura)", "m": 0.8769, "x": 2.6855, "r_e": 0.158, "r_i": 0.079,
     "l": 0.210}
]

cg_global = 1.35069
I_xx_total = 0
I_yy_total = 0

for c in componentes:
    # 1. Inércia Intrínseca Transversal (Cilindro/Tubo/Disco)
    i_intr_yy = (c["m"] / 12) * (3 * (c["r_e"] ** 2 + c["r_i"] ** 2) + c["l"] ** 2)

    # 2. Teorema dos Eixos Paralelos (Steiner)
    d = abs(c["x"] - cg_global)
    steiner = c["m"] * (d ** 2)
    I_yy_total += (i_intr_yy + steiner)

    # 3. Inércia Intrínseca Longitudinal
    I_xx_total += 0.5 * c["m"] * (c["r_e"] ** 2 + c["r_i"] ** 2)

print(f"Inércia Seca - I_xx (Roll): {I_xx_total:.3f} kg*m^2 | I_yy/I_zz (Pitch/Yaw): {I_yy_total:.3f} kg*m^2")