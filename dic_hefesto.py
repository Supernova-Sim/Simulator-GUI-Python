from pyprojroot import here

caminho_raiz = here()


caminho_data = caminho_raiz / "data"


setting = {
    # Foguete Base

    "radius": 0.079, # m - open rocket
    "mass": 21.644, # kg abaixo - open rocket
    "coordinate_system_orientation": "nose_to_tail",

    # e preciso checar se os eixos estao invertidos, o inertia devolve em outra ordem
    "inertia": (11.784, 11.784, 0.099), # Calculado

    "center_of_mass_without_motor": 1.35, # m - OpenRocket without motorDic ##

    # Arrasto

    "power_off_drag": str(caminho_data  / "power_off.csv") , # (RasAero II)
    "power_on_drag": str(caminho_data  / "power_on.csv"), #

}

aletasDic = {
    # Aletas (Fins)

    "n": 4,
    "position": 2.57,  # m - openrocket

    # COORDENADAS EXTRAÍDAS # AUTO
    "shape_points": [
        (0.0, 0.0),
        (0.07, 0.12),
        (0.21, 0.14),
        (0.18, 0.0)
    ]
}

coifaDic = {
   # Coifa (Nosecone)

    "length": 0.45,  # m - openrocket
    "position": 0,  # m
    "kind": "lvhaack"  ## checar
}

rail_buttonDic = {
    # Rail Buttons (Guias)

    "upper_button_position": 1.39,  # m
    "lower_button_position": 2.30,  # m
    "angular_position": 45.0,  # graus
    "radius": 0.02,  # m
}

refeedRecDic = {

    "name": "reefed",
    "cd_s": 0.85,  #
    "radius": 1.2 / 2,  # m
    "trigger": "apogee",  # m
    "lag": 1  # s

}

unrefeedRecDic = {

    "name": "unreefed",
    "cd_s": 1.5,  #
    "radius": 3.8000000000000003 / 2,  # openrocket
    "trigger": 450,  # openrocket
    "lag": 1  # openrocket

}

##############################################

settingE = {

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

coifaE = {

    "length": 0.001, # 1 mm: hipótese de tolerância dimensional/comprimento medido
}

coifa_positionE = 0.001 # 1 mm: incerteza da referência axial de montagem da coifa

#

aletasE = {

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

aletas_positionE = 0.002

aletas_equivalentesTrapezio = {
    # é equivalente aerodinamicamente, mas nao é equivalente a aleta original freeform (obtido por otimizacao)
    "n": 4,
    "root_chord": 0.18,
    "tip_chord": 0.07458606,
    "span": 0.13999711,
    "sweep_length": 0.10051811,
    "position": 2.57,
    "cant_angle": 0.0,
}

railButtonE = {

    "buttons_distance": 0.002, # 2 mm: hipótese de erro na distância entre os dois rail buttons

    "angular_position": 1.0, # 1°: hipótese de desalinhamento angular durante a montagem
}

lower_button_positionE = 0.002

reefedRecE = {

    "cd_s": 0.085, # 10% de 0.85 m²: hipótese inicial de dispersão aerodinâmica do paraquedas

    "lag": 0.10,  # 0.10 s: hipótese de dispersão no tempo de inflação/acionamento
}

unreefedRecE = {

    "cd_s": 0.15, # 10% de 1.50 m²: hipótese inicial de dispersão do CdS aberto

    "lag": 0.10, # 0.10 s: hipótese de variação no processo de abertura
}