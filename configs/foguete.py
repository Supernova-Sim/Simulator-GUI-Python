from hefesto.paths import ARRASTO

MOTOR_POSITION = 2.78

# ---- Geometria nominal ----
FOGUETE = {
    "radius": 0.079,
    "mass": 21.644,
    "coordinate_system_orientation": "nose_to_tail",
    "inertia": (11.784, 11.784, 0.099),
    "center_of_mass_without_motor": 1.35,
    "power_off_drag": str(ARRASTO / "power_off.csv"),
    "power_on_drag":  str(ARRASTO / "power_on.csv"),
}

ALETAS = {
    "n": 4,
    "position": 2.57,
    "shape_points": [(0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)],
}

COIFA = {"length": 0.45, "position": 0, "kind": "lvhaack"}

RAIL_BUTTONS = {
    "upper_button_position": 1.39,
    "lower_button_position": 2.30,
    "angular_position": 45.0,
    "radius": 0.02,
}

REEFED   = {"name": "reefed",   "cd_s": 0.85, "radius": 0.6,             "trigger": "apogee", "lag": 1}
UNREEFED = {"name": "unreefed", "cd_s": 1.5,  "radius": 3.8 / 2,         "trigger": 450,      "lag": 1}

# Aletas trapezoidais equivalentes (substitui o trabalho do osweep/teste)
ALETAS_TRAPEZIO_EQUIV = {
    "n": 4,
    "root_chord": 0.18,
    "tip_chord": 0.07458606,
    "span": 0.13999711,
    "sweep_length": 0.10051811,
    "position": 2.57,
    "cant_angle": 0.0,
}



###

FOGUETE_E = {

    "radius": 0.0005, # 0.5 mm: hipótese de incerteza dimensional do diâmetro externo

    "mass": 0.10, # 0.10 kg: hipótese conservadora para massa seca de 21.644 kg

    "inertia_11": 11.784 * 0.05, # 5%: tensor foi calculado a partir de modelo geométrico/massas aproximadas

    "inertia_22": 11.784 * 0.05, # 5%: mesma incerteza de modelagem do outro eixo transversal

    "inertia_33": 0.099 * 0.05, # 5%: incerteza de modelagem da inércia longitudinal

    "center_of_mass_without_motor": 0.010, # 1 cm: hipótese inicial para erro na determinação do CG


    # Multiplicadores das curvas do RASAero
    "power_off_drag_factor": (1.0, 0.10), # 10%: incerteza inicial do modelo aerodinâmico sem empuxo

    "power_on_drag_factor": (1.0, 0.10), # 10%: incerteza inicial do modelo aerodinâmico com motorDic queimando
}

COIFA_E = {

    "length": 0.001, # 1 mm: hipótese de tolerância dimensional/comprimento medido
}

COIFA_POS_E = 0.001 # 1 mm: incerteza da referência axial de montagem da coifa

#

ALETAS_E = {

    "root_chord": 0.0005,
    # 0.5 mm: hipótese de incerteza equivalente na corda da raiz

    "tip_chord": 0.0005,
    # 0.5 mm: hipótese de incerteza equivalente na corda da ponta

    "span": 0.0005,
    # 0.5 mm: hipótese de incerteza equivalente na extensão radial

    "sweep_length": 0.0005,
    # 0.5 mm: hipótese de incerteza equivalente no sweep

    "cant_angle": 0.5,
    # 0.5°: hipótese de desalinhamento angular na montagem
}

ALETAS_POS_E = 0.002



RAIL_BUTTONS_E = {

    "buttons_distance": 0.002, # 2 mm: hipótese de erro na distância entre os dois rail buttons

    "angular_position": 1.0, # 1°: hipótese de desalinhamento angular durante a montagem
}

LOWER_BUTTON_POSITION_E = 0.002

REEFED_E = {

    "cd_s": 0.085, # 10% de 0.85 m²: hipótese inicial de dispersão aerodinâmica do paraquedas

    "lag": 0.10,  # 0.10 s: hipótese de dispersão no tempo de inflação/acionamento
}

UNREEFED_E = {

    "cd_s": 0.15, # 10% de 1.50 m²: hipótese inicial de dispersão do CdS aberto

    "lag": 0.10,  # 0.10 s: hipótese de variação no processo de abertura
}