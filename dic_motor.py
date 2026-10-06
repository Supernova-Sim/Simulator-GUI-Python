from pyprojroot import here

caminho_raiz = here()
caminho_data = caminho_raiz / "data"

motorDic = {

    "thrust_source": str(caminho_data / "jul1semMedidas.eng"),

    "dry_mass": 10,  # 21 - 11 (mA - mP)
    "dry_inertia": (1.47, 1.47, 0.0125),  #
    "center_of_dry_mass_position": 0.499,  # m

    "grain_number": 7,  # OpenMotor

    "grain_outer_radius": 0.04933, #0.05,  # OpenMotor
    "grain_initial_inner_radius": 0.0227, #0.02343,  # media ponderada entre os raios obtidos anteriormente
    "grain_initial_height": 0.15,  # OpenMotor "Length"
    "grain_separation": 0.01,  #

    "grain_density": 1842.44,  #
    "grains_center_of_mass_position": 0.67,  #

    "nozzle_position": 0.016,  #
    "nozzle_radius": 0.039,  #

    "throat_radius": 0.017, #0.0173,  # OpenMotor

    "burn_time": (0, 3.75),

    "coordinate_system_orientation": "nozzle_to_combustion_chamber",

}

############# Monte Carlo


motorE = {

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

motor_positionE = 0.002 # 2 mm: incerteza de montagem da posição axial do motorDic


