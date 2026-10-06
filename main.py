from rocketpy import Flight, Rocket, SolidMotor, MonteCarlo
from dic_hefesto import setting, aletasDic, coifaDic, rail_buttonDic, refeedRecDic, unrefeedRecDic, settingE, coifaE, railButtonE, reefedRecE, unreefedRecE
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

from rocketpy import Function


#compensa criar um arquivo py só para instanciar essas coisas e o main ficar só para executar comandos relacionados ao voo e etc?

#
from copy import deepcopy
from rocketpy import StochasticRocket

import numpy as np
import matplotlib.pyplot as plt

#



motor = SolidMotor(**motorDic)


# for per in range(80, 101):
#     fator = per / 100
#
#     motorDic["thrust_source"] = motor.thrust * fator
#     motorFor = SolidMotor(**motorDic)
#
#     foguete = Rocket(**setting)
#     nose =foguete.add_nose(**coifaDic)
#     fins = foguete.add_free_form_fins(**aletasDic)
#     rail_buttons = foguete.set_rail_buttons(**rail_buttonDic)
#     unreefed = foguete.add_parachute(**unrefeedRecDic)
#     reefed = foguete.add_parachute(**refeedRecDic)
#
#
#
#     foguete.add_motor(motorFor, position=2.78)
#
#     vooIrec_obj = Flight(
#         rocket=foguete,
#         environment=envIrec,
#         **vooIrecConfig,
#     )
#
#     #---#
#
#     print(vooIrec_obj.apogee - 1401 , " " , fator * 12600)


############################################################


motor = SolidMotor(**motorDic)



fogueteTest = Rocket(**setting)

setting["power_off_drag"] = fogueteTest.power_off_drag * 0.90
setting["power_on_drag"] = fogueteTest.power_on_drag * 0.90
foguete = Rocket(**setting)



nose =foguete.add_nose(**coifaDic)
fins = foguete.add_free_form_fins(**aletasDic)
rail_buttons = foguete.set_rail_buttons(**rail_buttonDic)
unreefed = foguete.add_parachute(**unrefeedRecDic)
reefed = foguete.add_parachute(**refeedRecDic)



foguete.add_motor(motor, position=2.78)

vooIrec_obj = Flight(
    rocket=foguete,
    environment=envIrec,
    **vooIrecConfig,
)

#---#

print(vooIrec_obj.apogee - 1401 , " " )








#####

# monte carlo nao tem a classe FreeFormFins, entao atualmente é preciso substituir por uma aleta trapezoidal bem semelhante


# mc_irec = MonteCarlo(
#     filename="resultados/irec",
#     environment=envIrec_estocastico,
#     rocket=foguete_estocastico,
#     flight=vooIrec_estocastico,
# )

# mc_irec.simulate(
#     number_of_simulations=10,
#     append=False,
#     parallel=False,
#
# )

#


