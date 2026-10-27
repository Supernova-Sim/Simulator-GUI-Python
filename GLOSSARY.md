# Hefesto — Simulação de Foguetes

Simulação integrada de balística interna de motores sólidos, propriedades de massa/inércia e dinâmica de voo de foguetes de sondagem para a IREC.

## Linguagem de Domínio

### Especificação vs. Derivação

**Spec (Especificação)**:
Contrato imutável de entrada que declara dimensões geométricas, materiais, caminhos de arquivos de fonte (`.ric`, `.eng`, `.csv`) e parâmetros nominais, sem valores calculados.
_Avoid_: DTO, schema, config bruta

**Derivado**:
Resultado imutável produzido por um cálculo físico ou simulação a partir de uma Spec (ex.: `MotorDerivado`, `ComponenteDerivado`, `CoifaDerivada`, `AletaDerivada`).
_Avoid_: model calculado, output, processado

**Foguete Resolvido (`FogueteResolvido`)**:
Agregação analítica de todos os componentes derivados do corpo, coifa e aletas, fornecendo massa seca total, centro de gravidade (CG) sem motor e momentos de inércia calculados pelo Teorema de Steiner.
_Avoid_: foguete derivado, estrutura agregada

**Foguete Montado (`FogueteMontado`)**:
Instância pronta para simulação de voo contendo os objetos `Rocket` e `SolidMotor` do RocketPy já acoplados aos subsistemas aerodinâmicos e de recuperação.
_Avoid_: rocket wrapper, instância RocketPy

### Modos de Representação do Foguete

**Modo Calculado (`calculado`)**:
Modo de construção em que massa seca, CG e momentos de inércia do foguete são derivados analiticamente a partir da soma de `COMPONENTES`, `CoifaSpec` e `AletaSpec`.
_Avoid_: modo spec_aleta, modo analítico implícito

**Modo Medido (`medido`)**:
Modo de construção em que massa seca, CG e momentos de inércia do foguete vêm de medições diretas de bancada ou exportação consolidada (`GeometriaMedidaSpec`).
_Avoid_: modo hardcoded, modo sem spec_aleta

### Motor e Balística Interna

**Fonte `.ric`**:
Arquivo do OpenMotor contendo geometria dos grãos propelentes, tubeira e propriedades balísticas do propelente, usado para simular pressão na câmara ($P_0$), razão de áreas ($K_n$), fluxo de massa e curva de empuxo.
_Avoid_: arquivo YAML do motor

**Fonte `.eng`**:
Arquivo RASP contendo apenas a curva de empuxo tabulada $(t, F)$ e metadados básicos, utilizado como fallback quando não há simulação de balística interna.
_Avoid_: curva de texto

**Override de Motor (`overrides`)**:
Dicionário de caminhos *dot-path* (com suporte a wildcard `*`) aplicado em memória sobre a estrutura do `.ric` antes da extração geométrica e da simulação balística para estudos paramétricos.
_Avoid_: mutação de arquivo, patch do motor

**Diagnóstico de Segurança (`DiagnosticoFS`)**:
Avaliação de um critério operacional ou estrutural (como Fator de Segurança da carcaça, $P_0$ máximo, $K_n$ máximo ou fluxo de massa máximo) frente aos limites de projeto (`LimitesSeguranca`).
_Avoid_: alerta solto, exceção de limite

### Sistemas de Referência e Convenções Físicas

**Referencial Axial do Foguete**:
Sistema `nose_to_tail` com origem $x = 0$ na ponta da coifa (nariz) e eixo positivo apontando para a cauda (tubeira).

**Referencial Interno do Motor**:
Nos cálculos internos de grãos (`MotorDerivado`), $x = 0$ fica no topo do motor (*forward closure*) e $x = \text{case\_length}$ na extremidade da tubeira; na montagem do `SolidMotor` do RocketPy (`nozzle_to_combustion_chamber`), as posições de CG são convertidas para distância a partir da tubeira ($\text{case\_length} - x_{\text{local}}$).

**Tensor de Inércia Principal (`(I_11, I_22, I_33)`)**:
Tupla de momentos principais de inércia seguindo a convenção do RocketPy, onde $e_3$ é o eixo longitudinal de simetria (roll) e $e_1, e_2$ são os eixos transversais ortogonais (pitch e yaw): `(I_transversal, I_transversal, I_longitudinal)`.
_Avoid_: `(I_xx, I_yy, I_zz)` ambíguo sem indicar qual eixo é roll
