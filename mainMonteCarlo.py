from rocketpy import Flight, Rocket, SolidMotor, MonteCarlo, StochasticTrapezoidalFins
from dic_hefesto import setting, aletasDic, coifaDic, rail_buttonDic, refeedRecDic, unrefeedRecDic, settingE, coifaE, \
    railButtonE, reefedRecE, unreefedRecE, aletas_equivalentesTrapezio, aletasE, aletas_positionE, coifa_positionE, \
    lower_button_positionE
from dic_motor import motorDic, motorE, motor_positionE
from ambiente import envLasc, envIrec, caminho_data, ambienteIrecE, envIrecEs
from dic_voo import vooLascConfig, vooIrecConfig, vooLascE, vooIrecE
from rocketpy.stochastic import (
    StochasticSolidMotor,
    StochasticRocket,
    StochasticNoseCone,
    StochasticRailButtons,
    StochasticParachute,
    StochasticFlight,
    StochasticEnvironment,
)

from copy import deepcopy


#-----# deterministico

foguete = Rocket(**setting)

motor = SolidMotor(**motorDic)

nose =foguete.add_nose(**coifaDic)
fins = foguete.add_trapezoidal_fins(**aletas_equivalentesTrapezio)
rail_buttons = foguete.set_rail_buttons(**rail_buttonDic)
unreefed = foguete.add_parachute(**unrefeedRecDic)
reefed = foguete.add_parachute(**refeedRecDic)

foguete.add_motor(motor, position=2.78)

vooIrec_obj = Flight(
    rocket=foguete,
    environment=envIrec,
    **vooIrecConfig,
)



#---# estocastico

motor_estocastico = StochasticSolidMotor(
    solid_motor=motor,
    **motorE,
)

foguete_estocastico = StochasticRocket(
    rocket=foguete,
    **settingE,
)

foguete_estocastico.add_motor(
    motor_estocastico,
    position=motor_positionE,
)

aletas_est = StochasticTrapezoidalFins(
    trapezoidal_fins=fins,
    **aletasE,
)

coifa_est = StochasticNoseCone(
    nosecone=nose,
    **coifaE,
)

rail_est = StochasticRailButtons(
    rail_buttons=rail_buttons,
    **railButtonE,
)

reefed_estocastico = StochasticParachute(
    parachute=reefed,
    **reefedRecE,
)

unreefed_estocastico = StochasticParachute(
    parachute=unreefed,
    **unreefedRecE,
)

envIrec_estocastico = StochasticEnvironment(
    environment=envIrecEs,
    ensemble_member=list(range(envIrecEs.num_ensemble_members)),
    **ambienteIrecE,
)

#-#


foguete_estocastico.add_trapezoidal_fins(
    aletas_est,
    position=aletas_positionE,
)

foguete_estocastico.add_nose(
    coifa_est,
    position=coifa_positionE,
)

foguete_estocastico.set_rail_buttons(
    rail_est,
    lower_button_position=lower_button_positionE,
)

foguete_estocastico.add_parachute(
    reefed_estocastico
)

foguete_estocastico.add_parachute(
    unreefed_estocastico
)


#--#

vooIrec_estocastico = StochasticFlight(
    flight=vooIrec_obj,
    **vooIrecE,
)

# testar uma brincadeira
data_collector = {
    "apogee_agl": lambda flight:
        flight.apogee - flight.env.elevation,
}
#
mc_irec = MonteCarlo(
    filename="resultados/irec",
    environment=envIrec_estocastico,
    rocket=foguete_estocastico,
    flight=vooIrec_estocastico,
    data_collector=data_collector,
)

# mc_irec.simulate(
#     number_of_simulations=20,
#     append=False,
#     parallel=True,
#     n_workers=4,
# )
#
# mc_irec.all_info()

#print(mc_irec.results["apogee"])

