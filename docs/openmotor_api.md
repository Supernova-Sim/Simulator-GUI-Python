# Referência da API do OpenMotor (`motorlib` + `uilib.fileIO`)

> **Fonte:** extraída do código real, openMotor **0.6.2**, commit `dcc7fd62045d55036451b833f60e16a786f4685d`
> (o mesmo fixado em `pyproject.toml`). Código local: `.venv/lib/python3.12/site-packages/motorlib/`.
> **Unidades:** tudo em SI (m, kg, Pa, s, N). **Exceção:** ângulos do bocal em graus. A unidade
> de cada propriedade está nas tabelas abaixo.
> **Se algo aqui divergir do código instalado, o código vence.** Veja "Como verificar" no fim.

## 1. Visão geral

```
uilib.fileIO.loadFile(path, fileTypes.MOTOR) ─► dict ─► Motor(dict) ─► motor.runSimulation() ─► SimulationResult
      (.ric, YAML + migração de versão)        (props)                      (canais + alerts + success)
```

- `from motorlib.motor import Motor` / `from uilib.fileIO import loadFile, fileTypes`.
- `uilib.fileIO` importa **PyQt6** e imprime linhas `[LOG]` no stdout/stderr (logger do uilib).
  Por isso o projeto tem o *hack* de `matplotlib.use` em `src/calculos/motorlib_wrapper.py`.
- `loadFile` usa `yaml.Loader` (**não é seguro**) e migra arquivos de versões antigas. Já
  `src/parsers/openmotor.py` lê o `.ric` com um `SafeLoader` customizado, sem importar o uilib.

## 2. Estrutura do dict do motor (= conteúdo do `.ric` sob `data`)

`Motor.getDict()` / `Motor.applyDict()` / `Motor(propDict)` usam exatamente este formato:

```python
{
  "config":    {ambPressure, burnoutThrustThres, burnoutWebThres, flowSeparationWarnPercent,
                mapDim, maxMachNumber, maxMassFlux, maxPressure, minPortThroat, sepPressureRatio, timestep},
  "nozzle":    {throat, exit, efficiency, divAngle, convAngle, throatLength, slagCoeff, erosionCoeff},
  "propellant": {"name": str, "density": kg/m³, "tabs": [ {minPressure, maxPressure, a, n, k, t, m}, ... ]}  # ou None
  "grains":    [ {"type": "BATES", "properties": {diameter, length, inhibitedEnds, coreDiameter}}, ... ],
}
```

Exemplo real (`MotorNovo2.ric`): 6 grãos `BATES` (D=0,09869 m, L=0,16 m, núcleo 0,041 m, `inhibitedEnds="Neither"`),
garganta 0,034 m, saída 0,078 m, propelente "Nakka - KNSB (2)" (ρ=1841 kg/m³, 1 tab).

Regras (de `PropertyCollection.setProperties`):
- Chaves desconhecidas são **ignoradas em silêncio** (typo no nome da propriedade não dá erro!).
- `FloatProperty`/`IntProperty.setValue`: se o valor está fora de `[min, max]`, ele é **ignorado em silêncio**
  e a propriedade mantém o valor anterior. Num objeto novo, esse valor é o **`min`** do range. Não há clamp nem erro.
  Exemplo verificado: `Nozzle().setProperties({"throat": 99})` deixa `throat == 0`.
- `EnumProperty.setValue`: valor fora da lista também é **ignorado em silêncio** (mantém o anterior, ou o 1º valor da lista).

## 3. `Motor` (`motorlib/motor.py`)

Atributos: `grains: list[Grain]`, `propellant: Propellant | None`, `nozzle: Nozzle`, `config: MotorConfig`.

| Método | Descrição |
|---|---|
| `Motor(propDict=None)` | Cria e, se houver dict, chama `applyDict`. |
| `getDict()` / `applyDict(d)` | Serializa e carrega o formato da seção 2. |
| `runSimulation(callback=None) -> SimulationResult` | Roda o solver. `callback(progresso 0..1)` retornando `True` **cancela** (devolve `simRes` parcial com `success=False`). |
| `getQuickResults() -> dict` | Sem simular: `volumeLoading` (%), `initialKn`, `propellantMass` (kg), `portRatio`, `length`, `diameter`. Devolve zeros se houver erro de geometria. |
| `calcKN(regDepth, dThroat)` | Kn = área queimando / área da garganta. `regDepth` = lista, 1 valor por grão. |
| `calcBurningSurfaceArea(regDepth)` | Soma das áreas de queima, só dos grãos com web restante. |
| `calcIdealPressure(regDepth, dThroat, kn=None)` | Pressão de equilíbrio (Pa) via `propellant.getPressureFromKn`. |
| `calcForce(chamberPres, dThroat, exitPres=None)` | Empuxo (N), `max(F, 0)`. |
| `calcFreeVolume(regDepth)` / `calcTotalVolume()` | Volume livre / volume do cilindro envolvente (m³). |
| `calcMachNumber(chamberPres, massFlux)` | Mach no núcleo do grão. |

**Semântica do `success`** (importante): em `runSimulation`, erros de pré-checagem (0 grãos, `EndBurningGrain` fora da
posição 0, erros de geometria, falta de propelente) retornam `simRes` **sem rodar**, com `success=False` e `alerts`
com nível `ERROR`. `success=True` é setado ao fim da integração. Depois disso são **adicionados alerts**:
`WARNING` (mass flux, pressão máxima, Mach, port/throat, separação de fluxo no bocal, pressão fora das tabs
do propelente) e até um `ERROR` ("Motor did not generate thrust"), **sem alterar o `success`**.
Ou seja, **`success=True` não significa "sem avisos nem erros"**. Confira `sim.alerts`.

## 4. `SimulationResult` (`motorlib/simResult.py`)

Atributos: `motor`, `alerts: list[SimAlert]`, `success: bool`, `channels: dict[str, LogChannel]`.

### Canais (`sim.channels[nome]`)
| Chave | Nome | Tipo | Unidade |
|---|---|---|---|
| `time` | Time | float | s |
| `kn` | Kn | float | — |
| `pressure` | Chamber Pressure | float | Pa |
| `force` | Thrust | float | N |
| `volumeLoading` | Volume Loading | float | % |
| `exitPressure` | Nozzle Exit Pressure | float | Pa |
| `dThroat` | Change in Throat Diameter | float | m |
| `mass` | Propellant Mass | **tuple por grão** | kg |
| `massFlow` | Mass Flow | tuple por grão | kg/s |
| `massFlux` | Mass Flux | tuple por grão | kg/(m²·s) |
| `regression` | Regression Depth | tuple por grão | m |
| `web` | Web | tuple por grão | m |
| `machNumber` | Core Mach Number | tuple por grão | — |

`LogChannel`: `getData(unit=None)` (converte se `unit` for dado), `getPoint(i)`, `getLast()`, `addData(x)`,
`getAverage()`, `getMax()`, `getMin()`. Nos canais "por grão", `getMax/Min` pegam o maior/menor valor individual.

### Métodos de `SimulationResult`
`getBurnTime()` (=último `time`), `getInitialKN()`, `getPeakKN()`, `getAveragePressure()`, `getMaxPressure()`,
`getMinExitPressure()`, `getPercentBelowThreshold(channel, threshold)`, `getImpulse(stop=None)`, `getAverageForce()`,
`getDesignation()` (ex.: "N3002"), `getFullDesignation()`, `getImpulseClassPercentage()`, `getPeakMassFlux()`,
`getPeakMassFluxLocation()`, `getPeakMachNumber()`, `getPeakMachNumberLocation()`, `getISP(index=None)`,
`getPortRatio()` (None se não houver porta), `getPropellantLength()`, `getMaxPropellantDiameter()`,
`getPropellantMass(index=0)`, `getVolumeLoading(index=0)`, `getIdealThrustCoefficient()`,
`getAdjustedThrustCoefficient()`, `getAlertsByLevel(level)`, `shouldContinueSim(thrustThres)`,
`getCSV(pref=None, exclude=[], excludeGrains=[])` (devolve **string** CSV), `addAlert(alert)`.

### Alertas
- `SimAlertLevel`: `ERROR`, `WARNING`, `MESSAGE`. `SimAlertType`: `GEOMETRY`, `CONSTRAINT`, `VALUE`.
- `SimAlert(level, alertType, description, location=None)`. O texto está em **`.description`**
  (não existe `.message`; o wrapper do projeto usa `getattr(a, 'message', str(a))`, que cai no `str(a)`).

## 5. `MotorConfig` (`motor.config`)

| Chave | Unidade | Range | Significado |
|---|---|---|---|
| `maxPressure` | Pa | 0 – 7e7 | Pressão máxima permitida (gera WARNING) |
| `maxMassFlux` | kg/(m²·s) | 0 – 1e4 | Mass flux máximo (WARNING) |
| `maxMachNumber` | — | 0 – 100 | Mach máximo no núcleo (WARNING) |
| `minPortThroat` | — | 1 – 4 | Razão mínima porta/garganta |
| `flowSeparationWarnPercent` | — | 0 – 1 | Limiar de aviso de separação de fluxo |
| `burnoutWebThres` | m | 2,54e-5 – 3,175e-3 | Web mínimo para considerar o grão queimando |
| `burnoutThrustThres` | % | 0,01 – 10 | Fim da simulação: empuxo < x % do máximo |
| `timestep` | s | 1e-4 – 0,1 | Passo de tempo |
| `ambPressure` | Pa | 1e-4 – 102000 | Pressão ambiente |
| `mapDim` | — (int) | 250 – 2000 | Resolução do mapa FMM dos grãos |
| `sepPressureRatio` | — | 1e-3 – 1 | Razão de pressão para separação de fluxo |

## 6. `Nozzle` (`motor.nozzle`)

Propriedades: `throat` (m), `exit` (m), `efficiency` (0–2), `divAngle` (deg), `convAngle` (deg), `throatLength` (m),
`slagCoeff` ((m·Pa)/s), `erosionCoeff` (m/(s·Pa)).

Métodos: `calcExpansion()`, `getThroatArea(dThroat=0)`, `getExitArea()`, `getExitPressure(k, inputPressure)`,
`getDivergenceLosses()`, `getThroatLosses(dThroat=0)`, `getSkinLosses()`,
`getIdealThrustCoeff(chamberPres, ambPres, gamma, dThroat, exitPres=None)`,
`getAdjustedThrustCoeff(chamberPres, ambPres, gamma, dThroat, exitPres=None)`, `getGeometryErrors()`,
`getDetailsString(lengthUnit='m')`. Também existe a função de módulo `eRatioFromPRatio(k, pRatio)`.

## 7. `Propellant` e `PropellantTab`

`Propellant(propDict=None)`: `name`, `density` (kg/m³, 1–10000), `tabs`.
`PropellantTab`: `minPressure`, `maxPressure` (Pa), `a` (m/(s·Pa^n), 1e-8–2), `n` (-0,99–0,99), `k` (1,000001–10, razão de calores
específicos), `t` (K), `m` (**g/mol**, 1e-6–100, massa molar dos gases de exaustão).

Métodos de `Propellant`: `getCStar(pressure)`, `getBurnRate(pressure)`, `getPressureFromKn(kn)`,
`getKnFromPressure(pressure)`, `getCombustionProperties(pressure)` (→ `a, n, gamma, T, molarMass`),
`getMinimumValidPressure()`, `getMaximumValidPressure()`, `getErrors()`, `getPressureErrors(pressure)`, `addTab(tab)`.

> Se a pressão da câmara sai de **todas** as faixas `(minPressure, maxPressure)` das tabs, `getPressureErrors` devolve um
> `WARNING` ("Chamber pressure deviated from propellant's entered ranges. Results may not be accurate."). A simulação
> **não é interrompida**. Só o primeiro ponto com pressão fora é reportado.

## 8. Grãos (`motorlib.grains.grainTypes`)

O dicionário `grainTypes` mapeia o **nome usado no `.ric`** (`"type"`) para a classe:

`'BATES'`, `'End Burner'`, `'Finocyl'`, `'Moon Burner'`, `'Star Grain'`, `'X Core'`, `'C Grain'`, `'D Grain'`,
`'Rod and Tube'`, `'Conical'`, `'Custom Grain'`.

Todos têm `diameter` (m, 0–6,6) e `length` (m, 0–24,6). `inhibitedEnds` ∈ `['Neither','Top','Bottom','Both']`
em todos, **exceto `End Burner`**. Propriedades específicas:

| Tipo (classe) | Propriedades específicas |
|---|---|
| `BATES` (`BatesGrain`) | `coreDiameter` (0–5 m) |
| `End Burner` (`EndBurningGrain`) | nenhuma. Deve ser o **primeiro** grão. |
| `Finocyl` | `numFins` (int 0–64), `finWidth`, `finLength`, `coreDiameter`, `invertedFins` (bool) |
| `Moon Burner` | `coreOffset`, `coreDiameter` |
| `Star Grain` | `numPoints` (int 0–64), `pointLength`, `pointWidth` |
| `X Core` | `slotWidth`, `slotLength` |
| `C Grain` | `slotWidth`, `slotOffset` (-6,6 – 6,6) |
| `D Grain` | `slotOffset` (-6,6 – 6,6) |
| `Rod and Tube` | `coreDiameter`, `rodDiameter`, `supportDiameter` |
| `Conical` | `forwardCoreDiameter`, `aftCoreDiameter` |
| `Custom Grain` | `points` (polígonos), `dxfUnit` ∈ `['m','cm','mm','in','ft']` |

Hierarquia: `Grain` → `PerforatedGrain` → `FmmGrain` (Finocyl, MoonBurner, Star, XCore, C, D, Custom usam
*fast marching* via `skfmm`, com mapa `mapDim × mapDim`; mais lentos). `BATES`, `Rod and Tube`
(`PerforatedGrain`), `Conical` e `End Burner` (`Grain`) têm geometria analítica.

API comum de `Grain` (todos recebem `regDist` = profundidade de regressão em m):
`getSurfaceAreaAtRegression`, `getVolumeAtRegression`, `getWebLeft`, `isWebLeft(regDist, burnoutThres=1e-5)`,
`getMassFlux(massIn, dTime, regDist, dRegDist, position, density)`,
`getPeakMassFlux(massIn, dTime, regDist, dRegDist, density)`, `getEndPositions(regDist)` → `(x_ini, x_fim)`,
`getPortArea`, `getRegressedLength`, `getVolumeSlice(regDist, dRegDist)`, `getGrainBoundingVolume()`,
`getFreeVolume(regDist)`, `getGeometryErrors()` (→ `list[SimAlert]`), `getDetailsString(lengthUnit='m')`,
`simulationSetup(config)` (**obrigatório antes** de usar grãos FMM/Perforated fora de `runSimulation`).

## 9. `PropertyCollection` / `properties`

Base de Motor config, Nozzle, Propellant, Grain: `props: dict[str, Property]`,
`setProperties(dict)`, `getProperties(list=None)`, `getProperty(nome)`, `setProperty(nome, valor)`.
Tipos: `FloatProperty(dispName, unit, min, max)`, `IntProperty`, `EnumProperty(dispName, values)`,
`StringProperty`, `BooleanProperty`, `PolygonProperty`, `TabularProperty`.

## 10. `uilib.fileIO`

`fileTypes`: `PREFERENCES=1`, `PROPELLANTS=2`, `MOTOR=3`, `RECENT_FILES=4`. `appVersion = (0, 6, 2)`.
`loadFile(path, dataType)` → só o `data`. Valida `type`/`version` e migra versões antigas (`doMigration`).
`saveFile(path, data, dataType)`. `getConfigPath()` → diretório de dados do usuário (cria se não existir).

## 11. `motorlib.units` e `motorlib.constants`

- `convert(quantity, originUnit, destUnit)`, `convertAll(list, o, d)`, `getConversion(o, d)`,
  `getAllConversions(unit)`, `convFormat(quantity, o, d, places=3)`. Unidades internas: m, m³, m/s, N, Ns, Pa, kg, kg/m³, ...
- `constants`: `gasConstant=8314.462618`, `standardGravity=9.80665`, `atmosphericPressure=101325`,
  `maximumRefLength=24.6`, `maximumRefDiameter=6.6`.
- `motorlib.geometry`: `circleArea`, `circlePerimeter`, `circleDiameterFromArea`, `tubeArea`, `cylinderArea`,
  `cylinderVolume`, `frustumLateralSurfaceArea`, `frustumVolume`, `splitFrustum`, ...

## 12. Uso no projeto Hefesto

| Arquivo | Uso |
|---|---|
| `src/calculos/motorlib_wrapper.py` | `carregar_props(ric)` → dict. `simular_props(props)` / `simular_ric(ric)` → `MotorResultado` (séries 1D/2D em SI + P0/Kn/mass-flux pico, impulso, Isp). |
| `src/calculos/motorlib_variacoes.py` | Varia propriedades do dict (`validar_overrides`, `simular_variacao`) |
| `src/parsers/openmotor.py` | Lê o `.ric` (YAML) → `RicMotorSpec` → `MotorSpec`, sem uilib |

Pegadinhas conhecidas:
1. `Motor(props)` **consome** o dict. Passe cópia (`copy.deepcopy`) se for reusar.
2. Typo em nome de propriedade é ignorado sem erro. Valide as chaves (`validar_overrides`).
3. Valores fora do range (e enums inválidos) são **ignorados** sem aviso, e a propriedade fica no valor anterior
   (o `min` num objeto novo). Confira os ranges das seções 5–8, principalmente `config`, que tem limites estreitos.
4. `success=True` não exclui `WARNING`s nem `ERROR`s adicionados ao final. Verifique `sim.alerts`.
5. Canais "por grão" retornam tuplas, e os 1D, floats. O wrapper normaliza com `_as_1d`/`_as_2d`.
6. `impulso_total` do wrapper é integrado por trapézio sobre `force`. Também existe `sim.getImpulse()`.

## 13. Como verificar (anti-alucinação)

```bash
# assinaturas e docstrings de uma classe/método:
uv run python -c "import inspect, motorlib.motor as m; print(inspect.signature(m.Motor.runSimulation)); print(inspect.getdoc(m.Motor.runSimulation))"
# propriedades (nome, tipo, unidade, range) de qualquer coleção:
uv run python -c "
from motorlib.nozzle import Nozzle
for k,p in Nozzle().props.items(): print(k, type(p).__name__, p.unit, p.dispName)"
# código-fonte: .venv/lib/python3.12/site-packages/motorlib/  (ou o repositório upstream no commit fixado)
```
