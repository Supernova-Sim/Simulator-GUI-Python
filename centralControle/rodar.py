#!/usr/bin/env python
"""CLI unificada do projeto.

Uso:
    python centralControle/rodar.py sim       # determinística
    python centralControle/rodar.py motor     # só o motor (sem voo)
    python centralControle/rodar.py fs        # só diagnósticos
    python centralControle/rodar.py varrer    # varredura
"""
import argparse
import sys
from pathlib import Path

# Garante o projeto no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def cmd_sim(args):
    import scripts.simDeterministica as sd
    sd.main()


# def cmd_motor(args):
#     from configs.foguetes.hefesto.motor import MOTOR_IREC
#     from src.calculos.motor import derivar_motor
#
#     d = derivar_motor(MOTOR_IREC)
#     print(f"--- {d.nome} (fonte: {d.fonte}) ---")
#     print(f"  burn_time:    {d.burn_time}")
#     print(f"  impulse:      {d.total_impulse:.1f} N·s")
#     print(f"  max_thrust:   {d.max_thrust:.1f} N")
#     print(f"  propellant:   {d.propellant_mass:.4f} kg")
#     print(f"  mass_loaded:  {d.mass_loaded:.4f} kg")
#     if d.p0_pico is not None:
#         print(f"  P0_pico:      {d.p0_pico/1e6:.3f} MPa")
#         print(f"  Kn_pico:      {d.kn_pico:.1f}")
#         print(f"  ISP:          {d.isp_entregue:.2f} s")


def cmd_fs(args):
    from configs import MOTOR_IREC
    from src.calculos.motor import derivar_motor

    d = derivar_motor(MOTOR_IREC)
    if not d.diagnosticos:
        print("Sem diagnósticos — fonte é .eng (falta balística interna).")
        return
    for diag in d.diagnosticos:
        print(diag.linha())
    ok = all(x.ok for x in d.diagnosticos)
    print()
    print("RESULTADO:", "✅ Todos passaram" if ok else "❌ Há alertas")


def cmd_varrer(args):
    import scripts.varredura as v
    v.main()

def cmd_dump(args):
    from centralControle.inspecionar import inspecionar_tudo
    inspecionar_tudo()

def cmd_motor(args):
    from centralControle.inspecionar import inspecionar_motor
    inspecionar_motor()


def cmd_estrutura(args):
    from centralControle.inspecionar import inspecionar_estrutura
    inspecionar_estrutura()


def cmd_smoke(args):
    from src.smoke import main as smoke_main
    smoke_main()


def main():
    p = argparse.ArgumentParser(description="Central de controle do projeto")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sim",    help="Simulação determinística").set_defaults(func=cmd_sim)
    sub.add_parser("motor",  help="Só o motor (sem voo)").set_defaults(func=cmd_motor)
    sub.add_parser("fs",     help="Diagnósticos de segurança").set_defaults(func=cmd_fs)
    sub.add_parser("varrer", help="Varredura paramétrica").set_defaults(func=cmd_varrer)
    sub.add_parser("dump", help="Imprime toda a configuração").set_defaults(func=cmd_dump)
    sub.add_parser("smoke", help="Smoke test dos módulos").set_defaults(func=cmd_smoke)
    sub.add_parser("motor", help="...").set_defaults(func=cmd_motor)
    sub.add_parser("estrutura", help="...").set_defaults(func=cmd_estrutura)
    sub.add_parser("dump", help="...").set_defaults(func=cmd_dump)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()