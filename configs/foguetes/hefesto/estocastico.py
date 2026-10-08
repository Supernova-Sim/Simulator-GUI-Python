# configs/foguetes/hefesto/estocastico.py
"""Parâmetros estocásticos (Monte Carlo) do Hefesto."""

FOGUETE_E = {
    "radius": 0.0005,
    "mass": 0.10,
    "inertia_11": 11.784 * 0.05,
    "inertia_22": 11.784 * 0.05,
    "inertia_33": 0.099 * 0.05,
    "center_of_mass_without_motor": 0.010,
    "power_off_drag_factor": (1.0, 0.10),
    "power_on_drag_factor":  (1.0, 0.10),
}

COIFA_E       = {"length": 0.001}
COIFA_POS_E   = 0.001

ALETAS_E = {
    "root_chord":   0.0005,
    "tip_chord":    0.0005,
    "span":         0.0005,
    "sweep_length": 0.0005,
    "cant_angle":   0.5,
}
ALETAS_POS_E = 0.002

RAIL_BUTTONS_E = {
    "buttons_distance":  0.002,
    "angular_position":  1.0,
}
LOWER_BUTTON_POSITION_E = 0.002

REEFED_E   = {"cd_s": 0.085, "lag": 0.10}
UNREEFED_E = {"cd_s": 0.15,  "lag": 0.10}

MOTOR_E = {

    "total_impulse": 0.03 * 12473.99,

    # Massa e propriedades inerciais
    "dry_mass": 0.05, # 0.05 kg: hipótese de incerteza de pesagem de ± algumas dezenas de gramas

    "dry_inertia_11": 1.47 * 0.05, # 5%: inércia obtida por modelagem e não por medição direta

    "dry_inertia_22": 1.47 * 0.05, # 5%: mesma incerteza do segundo eixo transversal

    "dry_inertia_33": 0.0125 * 0.05, # 5%: incerteza da inércia longitudinal


    "center_of_dry_mass_position": 0.005, # 5 mm: incerteza razoável para CG estimado/balanceado manualmente

    "grains_center_of_mass_position": 0.005,
    # 5 mm: acumula incertezas de posição, massa e espaçamento dos 7 grãos


    # Geometria dos grãos
    "grain_outer_radius": 0.0005, # 0.5 mm: hipótese de tolerância dimensional/fabricação do grão

    "grain_initial_inner_radius": 0.0005, # 0.5 mm: incerteza no raio médio do canal interno

    "grain_initial_height": 0.0005, # 0.5 mm: hipótese de erro de medição/corte do comprimento do grão

    "grain_separation": 0.0005, # 0.5 mm: hipótese de variação na montagem dos espaçadores


    # Propriedades do propelente
    "grain_density": 20, # 20 kg/m³: ~1.1% da densidade nominal, hipótese de variação do propelente


    # Tubeira
    "nozzle_radius": 0.0005, # 0.5 mm: hipótese de tolerância da geometria da saída

    "throat_radius": 0.0003, # 0.3 mm: garganta é mais sensível, assume-se medição/fabricação mais precisa

    "nozzle_position": 0.001, # 1 mm: incerteza na referência axial de montagem da tubeira


    # Queima
    "burn_out_time": 0.05, # 0.05 s: hipótese inicial de dispersão no tempo total de queima
}

MOTOR_POS_E = 0.002 # 2 mm: incerteza de montagem da posição axial do motorDic