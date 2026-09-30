import numpy as np
import matplotlib.pyplot as plt

from scipy.optimize import minimize_scalar
from rocketpy import Rocket

from dic_hefesto import setting, aletasDic as aletas, coifaDic as coifa


# ============================================================
# FREEFORM DE REFERÊNCIA
# ============================================================

rocket_free = Rocket(**setting)

rocket_free.add_nose(**coifa)

fins_free = rocket_free.add_free_form_fins(**aletas)


# ============================================================
# TRAPEZOIDAL COM ÁREA E AR EXATOS
# ============================================================

ROOT_CHORD = 0.18
TIP_CHORD = 0.11
SPAN = 0.14

POSITION = aletas["position"]

N_FINS = 4
CANT_ANGLE = 0.0


MACH_POINTS = np.linspace(0.0, 0.9, 10)


# ============================================================
# ALVOS
# ============================================================

AREA_ALVO = fins_free.Af
AR_ALVO = fins_free.AR
CPZ_ALVO = fins_free.cpz

CL_ALVO = np.array([
    fins_free.clalpha(mach)
    for mach in MACH_POINTS
])

CP_ROCKET_ALVO = np.array([
    rocket_free.cp_position(mach)
    for mach in MACH_POINTS
])


# ============================================================
# CRIA CANDIDATO
# ============================================================

def criar_candidato(sweep_length):

    rocket = Rocket(**setting)

    rocket.add_nose(**coifa)

    fins = rocket.add_trapezoidal_fins(
        n=N_FINS,
        root_chord=ROOT_CHORD,
        tip_chord=TIP_CHORD,
        span=SPAN,
        sweep_length=sweep_length,
        position=POSITION,
        cant_angle=CANT_ANGLE,
    )

    return rocket, fins


# ============================================================
# FUNÇÃO OBJETIVO
# ============================================================

def objetivo(sweep_length):

    rocket, fins = criar_candidato(sweep_length)

    # CP local da aleta
    erro_cpz_mm = (
        fins.cpz - CPZ_ALVO
    ) * 1000


    # Cl_alpha
    cl = np.array([
        fins.clalpha(mach)
        for mach in MACH_POINTS
    ])

    erro_cl_rel = (
        cl - CL_ALVO
    ) / CL_ALVO


    # CP global
    cp = np.array([
        rocket.cp_position(mach)
        for mach in MACH_POINTS
    ])

    erro_cp_global_mm = (
        cp - CP_ROCKET_ALVO
    ) * 1000


    # custo
    J = (
        erro_cpz_mm**2
        +
        np.mean(erro_cp_global_mm**2)
        +
        25 * np.mean(erro_cl_rel**2)
    )

    return J


# ============================================================
# OTIMIZA APENAS O SWEEP
# ============================================================

resultado = minimize_scalar(
    objetivo,
    bounds=(0.03, 0.14),
    method="bounded",
    options={
        "xatol": 1e-12,
    },
)


sweep_otimo = resultado.x


# ============================================================
# RESULTADO
# ============================================================

rocket_trap, fins_trap = criar_candidato(
    sweep_otimo
)


print("\n==========================================")
print("       TRAPEZOIDAL EQUIVALENTE")
print("==========================================")

print(f"root_chord:    {ROOT_CHORD:.8f} m")
print(f"tip_chord:     {TIP_CHORD:.8f} m")
print(f"span:          {SPAN:.8f} m")
print(f"sweep_length:  {sweep_otimo:.8f} m")

print("\nÁrea:")
print(f"FreeForm:      {fins_free.Af:.8f}")
print(f"Trapezoidal:   {fins_trap.Af:.8f}")

print("\nAR:")
print(f"FreeForm:      {fins_free.AR:.8f}")
print(f"Trapezoidal:   {fins_trap.AR:.8f}")

print("\nCP local:")
print(f"FreeForm:      {fins_free.cpz:.8f} m")
print(f"Trapezoidal:   {fins_trap.cpz:.8f} m")
print(
    "Diferença:     "
    f"{1000 * (fins_trap.cpz - fins_free.cpz):+.6f} mm"
)


# ============================================================
# CL_ALPHA
# ============================================================

print("\n==========================================")
print("             CL_ALPHA")
print("==========================================")

cl_free = []
cl_trap = []

for mach in MACH_POINTS:

    cf = fins_free.clalpha(mach)
    ct = fins_trap.clalpha(mach)

    cl_free.append(cf)
    cl_trap.append(ct)

    print(
        f"M={mach:.2f} | "
        f"Free={cf:.8f} | "
        f"Trap={ct:.8f} | "
        f"erro={100*(ct-cf)/cf:+.6f}%"
    )


# ============================================================
# CP GLOBAL
# ============================================================

print("\n==========================================")
print("           CP GLOBAL")
print("==========================================")

cp_free = []
cp_trap = []

for mach in MACH_POINTS:

    cpf = rocket_free.cp_position(mach)
    cpt = rocket_trap.cp_position(mach)

    cp_free.append(cpf)
    cp_trap.append(cpt)

    print(
        f"M={mach:.2f} | "
        f"Free={cpf:.8f} | "
        f"Trap={cpt:.8f} | "
        f"erro={1000*(cpt-cpf):+.6f} mm"
    )


# ============================================================
# DICIONÁRIO FINAL
# ============================================================

print("\n==========================================")
print("       DICIONÁRIO FINAL")
print("==========================================")

print("""
aletas_equivalentes = {
""")

print(f'    "n": {N_FINS},')
print(f'    "root_chord": {ROOT_CHORD:.8f},')
print(f'    "tip_chord": {TIP_CHORD:.8f},')
print(f'    "span": {SPAN:.8f},')
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
    label="Trapezoidal",
)

plt.xlabel("Mach")
plt.ylabel("Cl_alpha (1/rad)")
plt.title("Cl_alpha")

plt.grid()
plt.legend()

plt.show()


# ============================================================
# GRÁFICO ERRO CP
# ============================================================

erro_cp = (
    np.array(cp_trap)
    - np.array(cp_free)
) * 1000


plt.figure()

plt.plot(
    MACH_POINTS,
    erro_cp,
    marker="o",
)

plt.axhline(0)

plt.xlabel("Mach")
plt.ylabel("CP Trap - FreeForm (mm)")
plt.title("Erro do centro de pressão")

plt.grid()

plt.show()