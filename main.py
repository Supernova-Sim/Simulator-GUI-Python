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


#compensa criar um arquivo py só para instanciar essas coisas e o main ficar só para executar comandos relacionados ao voo e etc?

#
from copy import deepcopy
from rocketpy import StochasticRocket

import numpy as np
import matplotlib.pyplot as plt

#

foguete = Rocket(**setting)

motor = SolidMotor(**motorDic)

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


############################################################

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


