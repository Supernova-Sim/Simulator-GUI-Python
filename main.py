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


from copy import deepcopy
from rocketpy import StochasticRocket


class StochasticRocketComAletasFixas(StochasticRocket):

    def __init__(
        self,
        rocket,
        fixed_fins,
        fixed_fins_position,
        **kwargs,
    ):
        super().__init__(
            rocket=rocket,
            **kwargs,
        )

        self.fixed_fins = fixed_fins
        self.fixed_fins_position = fixed_fins_position


    def create_object(self):

        # Cria normalmente o foguete aleatório
        rocket = super().create_object()

        # Adiciona as FreeFormFins sem nenhuma aleatorização
        rocket.add_surfaces(
            deepcopy(self.fixed_fins),
            self.fixed_fins_position,
        )

        return rocket












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
motor_estocastico = StochasticSolidMotor(
    solid_motor=motor,
    **motorE,
)

foguete_estocastico = StochasticRocketComAletasFixas(
    rocket=foguete,
    **settingE,
    fixed_fins=fins,
    fixed_fins_position=2.57,
)

foguete_estocastico.add_motor(
    motor_estocastico,
    position=motor_positionE,
)

coifa_estocastica = StochasticNoseCone(
    nosecone=nose,
    **coifaE,
)

rail_estocastico = StochasticRailButtons(
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
#---#

vooIrec_estocastico = StochasticFlight(
    flight=vooIrec_obj,
    **vooIrecE,
)

############################################################

mc_irec = MonteCarlo(
    filename="resultados/irec",
    environment=envIrec_estocastico,
    rocket=foguete_estocastico,
    flight=vooIrec_estocastico,
)

# mc_irec.simulate(
#     number_of_simulations=10,
#     append=False,
#     parallel=False,
#
# )

mc_irec.all_info()
