"""Monte Carlo do voo IREC usando o Ensemble do ERA5."""
from rocketpy import Flight, MonteCarlo
from rocketpy.stochastic import (
    StochasticSolidMotor,
    StochasticRocket,
    StochasticNoseCone,
    StochasticRailButtons,
    StochasticParachute,
    StochasticFlight,
    StochasticEnvironment,
    StochasticTrapezoidalFins,
)

from hefesto.ambiente import build_irec, build_irec_ensemble
from hefesto.modelos import build_rocket
from hefesto.paths import RESULTADOS

from configs.foguete import (
    FOGUETE_E, COIFA_E, ALETAS_E, RAIL_BUTTONS_E,
    REEFED_E, UNREEFED_E,
    COIFA_POS_E, ALETAS_POS_E, LOWER_BUTTON_POSITION_E,
)
from configs.motor import MOTOR_E, MOTOR_POS_E
from configs.voo import IREC, IREC_E
from configs.ambiente import IREC_ENSEMBLE_E


def main() -> None:
    # ---------------------------------------------------------------
    # 1. Determinístico (base para cada Stochastic*)
    # ---------------------------------------------------------------
    det = build_rocket(tipo_aletas="trapezio")
    env_det = build_irec()

    voo_det = Flight(rocket=det.rocket, environment=env_det, **IREC)

    # ---------------------------------------------------------------
    # 2. Componentes estocásticos
    # ---------------------------------------------------------------
    motor_est = StochasticSolidMotor(solid_motor=det.motor, **MOTOR_E)

    foguete_est = StochasticRocket(rocket=det.rocket, **FOGUETE_E)
    foguete_est.add_motor(motor_est, position=MOTOR_POS_E)

    coifa_est  = StochasticNoseCone(nosecone=det.nosecone, **COIFA_E)
    aletas_est = StochasticTrapezoidalFins(trapezoidal_fins=det.fins, **ALETAS_E)
    rail_est   = StochasticRailButtons(rail_buttons=det.rail_buttons, **RAIL_BUTTONS_E)

    unreefed_est = StochasticParachute(parachute=det.unreefed, **UNREEFED_E)
    reefed_est   = StochasticParachute(parachute=det.reefed,   **REEFED_E)

    foguete_est.add_nose(coifa_est, position=COIFA_POS_E)
    foguete_est.add_trapezoidal_fins(aletas_est, position=ALETAS_POS_E)
    foguete_est.set_rail_buttons(
        rail_est, lower_button_position=LOWER_BUTTON_POSITION_E
    )
    # mesma ordem do build_rocket: unreefed antes de reefed
    foguete_est.add_parachute(unreefed_est)
    foguete_est.add_parachute(reefed_est)

    # ---------------------------------------------------------------
    # 3. Ambiente e voo estocásticos
    # ---------------------------------------------------------------
    env_ens = build_irec_ensemble()
    env_est = StochasticEnvironment(
        environment=env_ens,
        ensemble_member=list(range(env_ens.num_ensemble_members)),
        **IREC_ENSEMBLE_E,
    )

    voo_est = StochasticFlight(flight=voo_det, **IREC_E)

    # ---------------------------------------------------------------
    # 4. Monte Carlo
    # ---------------------------------------------------------------
    data_collector = {
        "apogee_agl": lambda f: f.apogee - f.env.elevation,
    }

    mc = MonteCarlo(
        filename=str(RESULTADOS / "irec"),
        environment=env_est,
        rocket=foguete_est,
        flight=voo_est,
        data_collector=data_collector,
    )

    mc.simulate(
        number_of_simulations=100,
        append=False,
        parallel=True,
        n_workers=4,
    )
    mc.all_info()


if __name__ == "__main__":
    main()