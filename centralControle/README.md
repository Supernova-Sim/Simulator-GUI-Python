# centralControle — painel do projeto

Este é o lugar onde você mexe. Todo o resto (`hefesto/`, `configs/`,
`scripts/`) é biblioteca ou configuração avançada — **não edite sem saber
o que faz**.

## Como simular

### Simulação determinística
    python centralControle/rodar.py sim

### Varredura (empuxo × arrasto)
    python centralControle/rodar.py varrer --empuxo 0.9..1.1 --arrasto 1.0

### Verificar motor sem voar
    python centralControle/rodar.py motor

### Diagnóstico de segurança (FS, P0, Kn, mass flux)
    python centralControle/rodar.py fs

## O que o código atual permite

- ✅ Simular voo completo (RocketPy) com atmosfera real (ERA5)
- ✅ Varredura paramétrica de empuxo/arrasto
- ✅ Rodar OpenMotor headless a partir do `.ric` e obter curva de empuxo
- ✅ Calcular FS da carcaça, P0 pico, Kn, mass flux
- ✅ Salvar JSON de cada simulação em `data/saida/`
- ⏳ Monte Carlo (reformulação pendente)
- ⏳ Parser `.ork` (OpenRocket)
- ⏳ Drag via RASAero (.CDX)
- ⏳ Análise de sensibilidade (Sobol, Morris)

## Mapa mental

    data/entrada/                 ← INPUT (não commitar grandes)
      openmotor/MotorNovo.ric     → OpenMotor: geometria do motor
      motores/jul1semMedidas.eng  → curvas de referência (cross-check)
      openrocket/rocket.ork       → geometria aérea (a integrar)
      arrasto/*.csv               → coeficientes de arrasto
      atmosfera/*.nc              → ERA5 ensemble

        ↓ (parsers)

    hefesto/parsers/              ← lê .ric, .eng, .ork
    hefesto/calculos/             ← derivações (motor, aletas, coifa, segurança)
    hefesto/modelo.py             ← agrega derivados no "foguete resolvido"
    hefesto/modelos.py            ← monta o Rocket() do RocketPy
    hefesto/ambiente.py           ← monta o Environment do RocketPy

        ↓ (execução)

    centralControle/rodar.py      ← PONTO DE ENTRADA

        ↓ (saída)

    data/saida/                   ← JSON de cada simulação, CSV de varredura


## Configuração do Medusa

Fluxo interno (motor)

.ric ─→ loadFile (OpenMotor) ─→ Motor ─→ runSimulation()
↓
curva_empuxo, P0_pico, Kn_pico, mass_flux_pico
↓
derivar_motor() ─→ MotorDerivado
↓
┌────────────────────────┴────────────────────────┐
↓ ↓
_motor_kwargs() diagnosticos
↓ ↓
SolidMotor (RocketPy) FS, P0, Kn, flux

**Arquivo:** `configs/motor/medusa.py`

    RIC_MEDUSA  = data/entrada/openmotor/MotorNovo.ric    ← geometria
    ENG_MEDUSA  = data/entrada/motores/jul1semMedidas.eng ← cross-check
    _CARCAÇA_MEDUSA = {
        case_inner_radius:   0.05395
        case_wall_thickness: 0.003175
        case_density:        2700     # Al 6063-T5
        grain_separation:    0.010
        nozzle_position:     0.016
        case_length:         1.100
        dry_mass:            7.5
    }

**Limites:** `configs/limites.py`

    FS_MIN_CARCACA     = 2.0
    P0_MAX             = 8.0e6
    KN_MAX             = 250
    MASS_FLUX_MAX      = 1406

## Checklist antes de simular oficial

- [ ] `.ric` do motor é a versão mais recente?
- [ ] `FS carcaça ≥ 2.0`?
- [ ] `P0 ≤ 8 MPa`?
- [ ] `Kn ≤ 250`?
- [ ] `mass flux ≤ 1406 kg/(m²·s)`?
- [ ] Atmosfera do dia corresponde (lat/lon/data)?

## Estrutura detalhada

(expandir conforme o projeto crescer)