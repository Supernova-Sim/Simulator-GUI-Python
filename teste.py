import numpy as np
import matplotlib.pyplot as plt

from scipy.optimize import differential_evolution
from rocketpy import Rocket, SolidMotor, Flight

from dic_hefesto import (
    setting,
    aletasDic,
    coifaDic,
    rail_buttonDic,
    refeedRecDic,
    unrefeedRecDic,
)

from dic_motor import motorDic as MotorD
from ambiente import envIrec


# ============================================================
# CONFIGURAÇÃO
# ============================================================

ROOT_CHORD = 0.18

N_FINS = 4

POSITION = aletasDic["position"]

CANT_ANGLE = 0.0


# Faixa de Mach relevante para o voo
MACH_POINTS = np.linspace(0.0, 0.9, 10)


# ============================================================
# CRIA MODELO DE REFERÊNCIA - FREEFORM
# ============================================================

def criar_referencia():

    rocket = Rocket(**setting)

    rocket.add_nose(**coifaDic)

    fins = rocket.add_free_form_fins(**aletasDic)

    return rocket, fins


rocket_free_ref, fins_free_ref = criar_referencia()


# ============================================================
# VALORES-ALVO
# ============================================================

AREA_ALVO = fins_free_ref.Af
CPZ_ALVO = fins_free_ref.cpz
AR_ALVO = fins_free_ref.AR

CLALPHA_ALVO = np.array([
    fins_free_ref.clalpha(mach)
    for mach in MACH_POINTS
])

CP_ROCKET_ALVO = np.array([
    rocket_free_ref.cp_position(mach)
    for mach in MACH_POINTS
])


print("\n==========================================")
print("        FREEFORM DE REFERÊNCIA")
print("==========================================")

print(f"Área:       {AREA_ALVO:.8f} m²")
print(f"CP local:   {CPZ_ALVO:.8f} m")
print(f"AR:         {AR_ALVO:.8f}")

print("\nCl_alpha:")
for mach, cl in zip(MACH_POINTS, CLALPHA_ALVO):
    print(f"Mach {mach:.2f}: {cl:.8f}")

print("\nCP global:")
for mach, cp in zip(MACH_POINTS, CP_ROCKET_ALVO):
    print(f"Mach {mach:.2f}: {cp:.8f} m")


# ============================================================
# CRIA UMA ALETA TRAPEZOIDAL CANDIDATA
# ============================================================

def criar_candidato(tip_chord, span, sweep_length):

    rocket = Rocket(**setting)

    rocket.add_nose(**coifaDic)

    fins = rocket.add_trapezoidal_fins(
        n=N_FINS,
        root_chord=ROOT_CHORD,
        tip_chord=tip_chord,
        span=span,
        sweep_length=sweep_length,
        position=POSITION,
        cant_angle=CANT_ANGLE,
    )

    return rocket, fins


# ============================================================
# FUNÇÃO OBJETIVO
# ============================================================

def objetivo(x):

    tip_chord, span, sweep_length = x

    try:
        rocket, fins = criar_candidato(
            tip_chord,
            span,
            sweep_length,
        )

        # ----------------------------------------------------
        # 1. Área
        # ----------------------------------------------------

        erro_area = (
            (fins.Af - AREA_ALVO)
            / AREA_ALVO
        )


        # ----------------------------------------------------
        # 2. Centro de pressão local da aleta
        #
        # normalizado por 1 mm:
        # 1.0 = erro de 1 mm
        # ----------------------------------------------------

        erro_cpz = (
            (fins.cpz - CPZ_ALVO)
            / 0.001
        )


        # ----------------------------------------------------
        # 3. Aspect ratio
        # ----------------------------------------------------

        erro_ar = (
            (fins.AR - AR_ALVO)
            / AR_ALVO
        )


        # ----------------------------------------------------
        # 4. Cl_alpha em vários Mach
        # ----------------------------------------------------

        clalpha = np.array([
            fins.clalpha(mach)
            for mach in MACH_POINTS
        ])

        erro_clalpha = (
            (clalpha - CLALPHA_ALVO)
            / CLALPHA_ALVO
        )


        # ----------------------------------------------------
        # 5. CP DO FOGUETE COMPLETO
        #
        # normalizado por 1 mm
        # ----------------------------------------------------

        cp_rocket = np.array([
            rocket.cp_position(mach)
            for mach in MACH_POINTS
        ])

        erro_cp_rocket = (
            (cp_rocket - CP_ROCKET_ALVO)
            / 0.001
        )


        # ====================================================
        # FUNÇÃO DE CUSTO
        # ====================================================
        #
        # CP recebe peso importante porque foi justamente
        # onde a aproximação anterior mais divergiu.
        #
        # Área e AR entram como restrições aerodinâmicas
        # complementares.
        # ====================================================

        J = (
            5.0 * erro_area**2
            +
            2.0 * erro_ar**2
            +
            2.0 * erro_cpz**2
            +
            10.0 * np.mean(erro_clalpha**2)
            +
            10.0 * np.mean(erro_cp_rocket**2)
        )

        return J

    except Exception:
        # Geometria inválida recebe penalidade enorme
        return 1e30


# ============================================================
# LIMITES DE BUSCA
# ============================================================
#
# Baseados na geometria original.
#
# FreeForm original:
#
# (0.00, 0.00)
# (0.07, 0.12)
# (0.21, 0.14)
# (0.18, 0.00)
#
# ============================================================

bounds = [
    # tip_chord
    (0.06, 0.18),

    # span
    (0.10, 0.17),

    # sweep_length
    (0.03, 0.13),
]


# ============================================================
# OTIMIZAÇÃO GLOBAL
# ============================================================

print("\n==========================================")
print("           INICIANDO OTIMIZAÇÃO")
print("==========================================\n")


resultado = differential_evolution(
    objetivo,
    bounds=bounds,

    strategy="best1bin",

    popsize=20,

    maxiter=300,

    tol=1e-9,

    polish=True,

    seed=42,

    workers=1,

    updating="immediate",
)


tip_otimo, span_otimo, sweep_otimo = resultado.x


print("\n==========================================")
print("          MELHOR GEOMETRIA")
print("==========================================")

print(f"tip_chord:    {tip_otimo:.8f} m")
print(f"span:         {span_otimo:.8f} m")
print(f"sweep_length: {sweep_otimo:.8f} m")

print(f"\nCusto final: {resultado.fun:.12e}")


# ============================================================
# CRIA A MELHOR ALETA
# ============================================================

rocket_trap_ref, fins_trap_ref = criar_candidato(
    tip_otimo,
    span_otimo,
    sweep_otimo,
)


# ============================================================
# COMPARAÇÃO DAS ALETAS
# ============================================================

print("\n==========================================")
print("        COMPARAÇÃO FINAL DAS ALETAS")
print("==========================================")

print("\nÁREA")

print(f"FreeForm:    {fins_free_ref.Af:.8f} m²")
print(f"Trapezoidal: {fins_trap_ref.Af:.8f} m²")

print(
    "Erro:        "
    f"{100 * (fins_trap_ref.Af - fins_free_ref.Af) / fins_free_ref.Af:+.6f} %"
)


print("\nCP LOCAL")

print(f"FreeForm:    {fins_free_ref.cpz:.8f} m")
print(f"Trapezoidal: {fins_trap_ref.cpz:.8f} m")

print(
    "Erro:        "
    f"{1000 * (fins_trap_ref.cpz - fins_free_ref.cpz):+.6f} mm"
)


print("\nASPECT RATIO")

print(f"FreeForm:    {fins_free_ref.AR:.8f}")
print(f"Trapezoidal: {fins_trap_ref.AR:.8f}")

print(
    "Erro:        "
    f"{100 * (fins_trap_ref.AR - fins_free_ref.AR) / fins_free_ref.AR:+.6f} %"
)


# ============================================================
# COMPARAÇÃO DE CL_ALPHA
# ============================================================

print("\n==========================================")
print("            CL_ALPHA × MACH")
print("==========================================")

cl_free = []
cl_trap = []

for mach in MACH_POINTS:

    cf = fins_free_ref.clalpha(mach)
    ct = fins_trap_ref.clalpha(mach)

    cl_free.append(cf)
    cl_trap.append(ct)

    erro = 100 * (ct - cf) / cf

    print(
        f"M={mach:.2f} | "
        f"Free={cf:.8f} | "
        f"Trap={ct:.8f} | "
        f"Erro={erro:+.5f}%"
    )


# ============================================================
# COMPARAÇÃO DO CP GLOBAL
# ============================================================

print("\n==========================================")
print("           CP DO FOGUETE × MACH")
print("==========================================")

cp_free = []
cp_trap = []

for mach in MACH_POINTS:

    cpf = rocket_free_ref.cp_position(mach)
    cpt = rocket_trap_ref.cp_position(mach)

    cp_free.append(cpf)
    cp_trap.append(cpt)

    erro_mm = 1000 * (cpt - cpf)

    print(
        f"M={mach:.2f} | "
        f"Free={cpf:.8f} m | "
        f"Trap={cpt:.8f} m | "
        f"Erro={erro_mm:+.4f} mm"
    )


# ============================================================
# DICIONÁRIO FINAL PARA COPIAR
# ============================================================

aletas_equivalentes = {

    "n": N_FINS,

    "root_chord": ROOT_CHORD,

    "tip_chord": float(tip_otimo),

    "span": float(span_otimo),

    "sweep_length": float(sweep_otimo),

    "position": POSITION,

    "cant_angle": CANT_ANGLE,
}


print("\n==========================================")
print("       DICIONÁRIO PARA O ROCKETPY")
print("==========================================\n")

print("aletas_equivalentes = {")
print(f'    "n": {N_FINS},')
print(f'    "root_chord": {ROOT_CHORD:.8f},')
print(f'    "tip_chord": {tip_otimo:.8f},')
print(f'    "span": {span_otimo:.8f},')
print(f'    "sweep_length": {sweep_otimo:.8f},')
print(f'    "position": {POSITION:.8f},')
print(f'    "cant_angle": {CANT_ANGLE:.8f},')
print("}")


# ============================================================
# GRÁFICO CL_ALPHA
# ============================================================

plt.figure()

plt.plot(
    MACH_POINTS,
    cl_free,
    marker="o",
    label="FreeForm",
)

plt.plot(
    MACH_POINTS,
    cl_trap,
    marker="o",
    label="Trapezoidal equivalente",
)

plt.xlabel("Mach")
plt.ylabel("Cl_alpha (1/rad)")
plt.title("Cl_alpha: FreeForm × Trapezoidal")

plt.grid()
plt.legend()

plt.show()


# ============================================================
# GRÁFICO DO ERRO DE CP GLOBAL
# ============================================================

erro_cp_mm = (
    np.array(cp_trap)
    - np.array(cp_free)
) * 1000


plt.figure()

plt.plot(
    MACH_POINTS,
    erro_cp_mm,
    marker="o",
)

plt.axhline(0)

plt.xlabel("Mach")
plt.ylabel("CP Trap - FreeForm (mm)")
plt.title("Erro do centro de pressão global")

plt.grid()

plt.show()


# ============================================================
# VALIDAÇÃO FINAL COM FLIGHT
# ============================================================

def criar_foguete_completo(tipo):

    rocket = Rocket(**setting)

    motor = SolidMotor(**MotorD)

    rocket.add_nose(**coifaDic)

    if tipo == "freeform":

        rocket.add_free_form_fins(**aletasDic)

    elif tipo == "trapezoidal":

        rocket.add_trapezoidal_fins(
            **aletas_equivalentes
        )

    else:

        raise ValueError(tipo)

    rocket.set_rail_buttons(**rail_buttonDic)

    rocket.add_parachute(**unrefeedRecDic)
    rocket.add_parachute(**refeedRecDic)

    rocket.add_motor(
        motor,
        position=2.78,
    )

    return rocket


rocket_free_final = criar_foguete_completo(
    "freeform"
)

rocket_trap_final = criar_foguete_completo(
    "trapezoidal"
)


voo_free = Flight(
    rocket=rocket_free_final,
    environment=envIrec,
    rail_length=6,
    inclination=71,
    heading=90,
    terminate_on_apogee=True,
)


voo_trap = Flight(
    rocket=rocket_trap_final,
    environment=envIrec,
    rail_length=6,
    inclination=71,
    heading=90,
    terminate_on_apogee=True,
)


# ============================================================
# RESULTADOS DO VOO
# ============================================================

apogeu_free = (
    voo_free.apogee
    - envIrec.elevation
)

apogeu_trap = (
    voo_trap.apogee
    - envIrec.elevation
)


print("\n==========================================")
print("        VALIDAÇÃO FINAL DO VOO")
print("==========================================")

print("\nAPOGEU AGL")

print(f"FreeForm:    {apogeu_free:.4f} m")
print(f"Trapezoidal: {apogeu_trap:.4f} m")
print(
    f"Diferença:   "
    f"{apogeu_trap - apogeu_free:+.4f} m"
)


print("\nMARGEM ESTÁTICA INICIAL")

print(
    f"FreeForm:    "
    f"{voo_free.initial_stability_margin:.6f} cal"
)

print(
    f"Trapezoidal: "
    f"{voo_trap.initial_stability_margin:.6f} cal"
)

print(
    f"Diferença:   "
    f"{voo_trap.initial_stability_margin - voo_free.initial_stability_margin:+.6f} cal"
)


print("\nMARGEM NA SAÍDA DO TRILHO")

print(
    f"FreeForm:    "
    f"{voo_free.out_of_rail_stability_margin:.6f} cal"
)

print(
    f"Trapezoidal: "
    f"{voo_trap.out_of_rail_stability_margin:.6f} cal"
)

print(
    f"Diferença:   "
    f"{voo_trap.out_of_rail_stability_margin - voo_free.out_of_rail_stability_margin:+.6f} cal"
)


print("\nCP MACH 0")

cp_free_0 = rocket_free_final.cp_position(0)
cp_trap_0 = rocket_trap_final.cp_position(0)

print(f"FreeForm:    {cp_free_0:.8f} m")
print(f"Trapezoidal: {cp_trap_0:.8f} m")

print(
    f"Diferença:   "
    f"{1000 * (cp_trap_0 - cp_free_0):+.5f} mm"
)