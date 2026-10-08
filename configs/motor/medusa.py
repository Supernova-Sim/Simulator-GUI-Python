# configs/motor_medusa.py
"""Configuração do motor Medusa (IREC).

Geometria do motor (grãos, tubeira, propelente) vem do .ric do OpenMotor.
Aqui ficam os complementos que o OpenMotor não carrega: carcaça, curva de
empuxo, posição da tubeira e separação entre grãos.
"""
from hefesto.parsers.openmotor import motor_spec_do_ric
from hefesto.paths import MOTORES, OPENMOTOR
from configs.motor.spec import MotorSpec


# ============================================================
#  Caminhos
# ============================================================
RIC_MEDUSA   = OPENMOTOR / "MotorNovo.ric"
ENG_MEDUSA   = MOTORES   / "jul1semMedidas.eng"


# ============================================================
#  Complementos que o .ric não carrega (medições do Medusa)
# ============================================================
_CARCAÇA_MEDUSA = dict(
    case_inner_radius  = 0.05395,
    case_wall_thickness= 0.003175,
    case_density       = 2700.0,     # alumínio 6063-T5

    grain_separation   = 0.010,
    nozzle_position    = 0.016,

    case_length        = 1.100,
    dry_mass           = 7.5,

    # Margens — usadas só se case_length=None
    margin_nozzle_side = 0.075,
    margin_forward_side= 0.075,
)


# ============================================================
#  Motor resolvido
# ============================================================
MOTOR_IREC: MotorSpec = motor_spec_do_ric(
    RIC_MEDUSA,
    thrust_curve_path = str(ENG_MEDUSA),   # cross-check mantido
    nome              = "Medusa KNSB",
    **_CARCAÇA_MEDUSA,
)