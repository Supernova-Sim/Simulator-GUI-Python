# configs/__init__.py
"""API pública de configs.

Consumidores importam `from configs import X`, nunca de submódulos.
Isso blinda o resto do projeto contra reorganizações internas.
"""

# ============================================================
#  ABSTRAÇÕES (formas)
# ============================================================
from configs.especificacao import AletaSpec, CoifaSpec
from configs.componentes import TuboSpec, MassaPontualSpec
from configs.motor.spec import MotorSpec, GrainSpec

# ============================================================
#  RECURSOS GLOBAIS
# ============================================================
from configs.material import (
    ALUMINIO_6061,
    FIBRA_CARBONO,
    COMPOSITO_G10,
    COMPOSITO_EFETIVO,
    COIFA_EFETIVA,
    SIGMA_LIM_AL6063_T5,
)
from configs.limites import (
    FS_MIN_CARCACA, FS_ALVO_CARCACA,
    FS_MIN_ALETAS, FS_MIN_ESTRUTURA, FS_MIN_RECUPERACAO,
    P0_MAX, KN_MAX, MASS_FLUX_MAX,
    PORT_THROAT_MIN, EROSION_MAX_GARGANTA,
)

# ============================================================
#  INSTÂNCIA: HEFESTO
# ============================================================
from configs.foguetes.hefesto import *   # noqa: F401, F403