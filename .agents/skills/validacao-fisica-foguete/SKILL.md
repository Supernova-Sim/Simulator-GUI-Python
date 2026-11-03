---
name: validacao-fisica-foguete
description: >
  Estratégia e padrões de validação física, matemática e numérica para simulações de
  foguetemodelismo (propulsão sólida/BATES, vasos de pressão, aerodinâmica de coifa/aletas,
  massa/inércia via Steiner e voo 6-DOF no RocketPy/openMotor). Ative sempre que criar,
  modificar ou testar métodos em src/calculos/, src/modelo.py, src/modelos.py, src/specs.py
  ou suítes em tests/.
---

# Validação Física e Numérica para Foguetemodelismo

Esta skill define como projetar e escrever casos de teste para validar simulações físicas e cálculos de engenharia aeroespacial no projeto **Hefesto**, combinando a estrutura enxuta do `pytest` (`@pytest.mark.parametrize`, `pytest.approx`, fixtures) com a filosofia do `ponytail` (zero dependências desnecessárias, código direto comentando apenas o *porquê* físico).

---

## 1. Regra de Ouro

**Nenhum método de simulação física é validado apenas por "rodar sem erro" ou por uma faixa arbitrária (`1.0 < x < 5.0`).**
Para validar um método físico, você nunca deve usar o próprio código testado para calcular o valor esperado. Todo método de cálculo deve ser verificado contra **4 Pilares de Validação**.

---

## 2. Os 4 Pilares Obrigatórios por Método Físico

Sempre que criar ou auditar uma função em `src/calculos/` ou `src/modelo.py`, estruture os testes cobrindo estes 4 pilares:

### Pilar 1 — Limite Analítico Exato (Fórmula Fechada)
Avalie a função em uma geometria simplificada ou caso degenerado cuja resposta matemática possa ser escrita à mão em 1 linha:
- **Por quê:** Garante que fatores de $\pi$, potências, conversões de raio/diâmetro e integrais não têm erros de sinal ou constantes faltando.
- **Exemplo:** Testar o integrador de polígono de aletas com um retângulo sem enflechamento ($c_r = c_t$, $\text{sweep} = 0$), onde a área exata é $b \cdot c_r$ e o centroide é $(c_r/2,\, b/2)$.

### Pilar 2 — Invariantes Físicos e Monotonicidade (`@pytest.mark.parametrize`)
Perturbe **1 parâmetro físico por vez** e verifique a direção obrigatória da variação ($\partial y / \partial x > 0$ ou $< 0$) e leis de conservação/simetria:
- **Escalonamento linear:** Dobrar a `densidade` de um componente deve dobrar sua `massa` e seus momentos de inércia ($I_{xx}, I_{yy}, I_{zz}$), mas **manter o `cg` idêntico** (`rel=1e-9`).
- **Invariância de translação/permutação:** Inverter a ordem da lista de componentes em `resolver()` não pode alterar `massa_seca`, `cg_sem_motor` nem `inercia`.
- **Monotonicidade balística:** Diminuir `throat_radius` deve aumentar $K_n$ e $P_0$; aumentar `coreDiameter` deve reduzir a massa de propelente e aumentar a área de queima inicial $A_b(0)$.

### Pilar 3 — Oráculo de Referência (Benchmark com Tolerância Explícita)
Compare a saída com um valor de referência externo (simulação openMotor `.ric` oficial do motor Medusa, tabela RASAero ou medição de bancada) declarando explicitamente a tolerância física esperada no `pytest.approx`.

### Pilar 4 — Fronteira Física Fail-Fast (`pytest.raises`)
Entradas fisicamente impossíveis devem falhar imediatamente no contrato (`src/specs.py` ou validação de fronteira) com `ValueError`:
- Raios, comprimentos, espessuras ou densidades $\le 0$;
- Geometrias invertidas ($r_{\text{interno}} \ge r_{\text{externo}}$, `espessura >= raio_externo`);
- Parâmetros de override fora da `WHITELIST` balística.

---

## 3. Tabela Oficial de Tolerâncias (`pytest.approx`)

Nunca use `pytest.approx(val)` sem refletir sobre a origem do erro numérico. Use as tolerâncias abaixo:

| Natureza do Cálculo | Tolerância Recomendada | Onde Aplica no Hefesto |
| :--- | :--- | :--- |
| **Álgebra exata / Geometria analítica / Conversão SI** | `rel=1e-9` | `TuboSpec`, `MassaPontualSpec`, `aletas.py` (polígono), `aletas_rasaero.py`, `seguranca.py`, Teorema de Steiner em `modelo.py` |
| **Quadratura numérica de perfil suave (`scipy.integrate.quad`)** | `rel=1e-4` | `coifa.py` (integração de superfície/momentos para perfis Von Kármán, Haack e Ogiva) |
| **Balística interna discretizada / Integração de voo 6-DOF** | `rel=1e-2` (1%) | `motor.py` (`openMotor` `.ric`/`.eng`), integral da curva $F(t)$, `Flight` no `RocketPy` |

---

## 4. Gabarito de Validação por Subsistema do Foguete

### A. Propulsão e Balística Interna (`src/calculos/motor.py`, `motorlib_*.py`)
1. **Conservação Geométrica da Massa de Propelente (Grãos BATES Cilíndricos):**
   $$m_{\text{prop}} = \rho_p \sum_{i=1}^{N} \pi \left(r_{e,i}^2 - r_{i,i}^2\right) L_i$$
   - *Teste:* Somar o volume dos `GrainSpec` em `MotorDerivado.grains`, multiplicar por `propellant_density` e exigir igualdade com `d.propellant_mass` (`rel=1e-6`).
2. **Consistência Impulso–Empuxo:**
   $$I_{\text{total}} = \int_{0}^{t_b} F(t)\,dt$$
   - *Teste:* Integrar `d.curva_empuxo` via `np.trapezoid(empuxos, tempos)` e comparar com `d.total_impulse` (`rel=1e-2`).
3. **Inércia do Motor Seco vs. Grãos (Simetria Cilíndrica):**
   - *Teste:* Em `d.dry_inertia`, exigir convenção RocketPy: $I_{11} == I_{22} > I_{33} > 0$.
4. **Sensibilidade Parametrizada de Overrides (`@pytest.mark.parametrize`):**
   - `throat` reduzido $\implies$ `throat_radius` cai exatamente na proporção, `kn_pico` sobe, `p0_pico` sobe.
   - `coreDiameter` aumentado $\implies$ `inner_radius` de todos os grãos sobe, `propellant_mass` cai.

### B. Segurança Estrutural (`src/calculos/seguranca.py`)
1. **Fórmula Analítica de Vaso de Pressão (Tensão Circunferencial / Hoop Stress):**
   $$\sigma_\theta = \frac{P_0 \cdot r_i}{t}, \qquad FS = \frac{\sigma_{\text{escoamento}}}{\sigma_\theta}$$
   - *Teste:* Para $P_0 = 2\,\text{MPa}$, $r_i = 0.05\,\text{m}$, $t = 0.002\,\text{m} \implies \sigma_\theta = 50\,\text{MPa}$. Se $\sigma_{\text{esc}} = 150\,\text{MPa}$, $FS = 3.0$ exato (`rel=1e-9`).
2. **Transição Exata de Fronteira (`ok=True` vs `ok=False`):**
   - *Teste:* Parametrizar valores exatamente em `limite * 0.999` e `limite * 1.001` para `check_p0`, `check_kn`, `check_mass_flux` e `fs_carcaca`.

### C. Aerodinâmica: Coifa (`src/calculos/coifa.py`)
1. **Condições de Contorno do Perfil $r(x)$:**
   - *Teste:* Em $x = 0$ (ponta), $r(0) == 0.0$; em $x = L$ (base), $r(L) == R_{\text{base}}$ (`rel=1e-9`) para todos os tipos (`vonkarman`, `lvhaack`, `ogive`, `conical`).
2. **Limite Analítico Cônico (`kind="conical"`):**
   - Área lateral de cone de parede fina: $A_{\text{lat}} = \pi R \sqrt{R^2 + L^2}$, massa $m \approx A_{\text{lat}} \cdot t \cdot \rho$, e $X_{\text{cg}} = \frac{2}{3} L$ a partir do vértice (`rel=1e-3`).
3. **Invariantes Físicos da Coifa:**
   - $0.5 L < X_{\text{cg}} < L$ (toda coifa afilada tem mais área perto da base do que da ponta);
   - Dobrar `densidade` dobra `massa`, `I_xx_local` e `I_yy_local`, mantendo `cg` constante.

### D. Aerodinâmica: Aletas (`src/calculos/aletas.py`, `aletas_rasaero.py`)
1. **Limite Analítico de Aleta Retangular (`root_chord == tip_chord`, `sweep_length == 0`):**
   - $\text{area\_planform} = b \cdot c_r$ (`rel=1e-9`);
   - $\text{massa\_uma} = b \cdot c_r \cdot t \cdot \rho$, $\text{massa\_total} = n \cdot \text{massa\_uma}$;
   - $X_{\text{cg,local}} = c_r / 2$, $Y_{\text{ma}} = b / 2$.
2. **Conversão e Geometria RASAero (`aleta_para_rasaero`):**
   - Conversão exata SI para polegadas: `chord_in * 0.0254 == chord_m` (`rel=1e-9`);
   - Sempre que `tip_chord < root_chord` e `sweep_length > 0`, validar geometricamente a relação trigonométrica entre `span_le`, `span_te`, `sweep_length` e as cordas.

### E. Componentes, Inércia Global e Montagem (`src/calculos/componentes.py`, `src/modelo.py`)
1. **Limite Analítico de Cilindro Oco (`derivar_tubo`):**
   - Volume exato $V = \pi (r_e^2 - r_i^2) L$, massa $m = \rho V$;
   - Momento de inércia polar/longitudinal exato: $I_{zz} = \frac{1}{2} m (r_e^2 + r_i^2)$ (`rel=1e-9`);
   - Momento transversal central: $I_{xx} = \frac{1}{12} m \left(3(r_e^2 + r_i^2) + L^2\right)$ (`rel=1e-9`).
2. **Teorema dos Eixos Paralelos (Steiner) em `resolver()`:**
   - *Teste:* Montar um foguete mínimo sintético com 2 massas pontuais idênticas $m$ nas posições $z_1 = -d$ e $z_2 = +d$ (com coifa/aleta de massa desprezível): o CG global deve cair em $z = 0$ e a inércia transversal deve somar $\sum m_i d_i^2 = 2 m d^2$.
3. **Invariância de Permutação:**
   - `resolver(componentes= list(reversed(COMPONENTES)), ...)` deve produzir `massa_seca`, `cg_sem_motor`, `inercia_transversal` e `inercia_longitudinal` idênticos a `resolver(componentes=COMPONENTES, ...)` (`rel=1e-9`).
4. **Convenção de Eixos do RocketPy:**
   - Em `FogueteResolvido.inercia_rocketpy` e `Rocket.I_11_without_motor`:
     $$I_{11} == I_{22} \quad \text{e} \quad I_{11} > 10 \cdot I_{33} > 0$$

---

## 5. Padrões de Escrita de Testes (`pytest` + `ponytail`)

1. **Nomenclatura Descritiva:**
   Use `test_<modulo_ou_funcao>_<cenario_fisico>_<propriedade_validada>()`:
   ```python
   def test_calcular_aleta_retangular_bate_com_formula_fechada() -> None: ...
   def test_derivar_tubo_dobra_massa_com_densidade_mantendo_cg() -> None: ...
   ```
2. **Parametrização em vez de Loops ou Duplicação:**
   ```python
   @pytest.mark.parametrize(
       ("fator_garganta", "espera_p0_maior"),
       [(0.94, True), (1.06, False)],
   )
   def test_motor_monotonicidade_garganta(fator_garganta: float, espera_p0_maior: bool) -> None:
       # testa se estreitar a garganta eleva P0 e alargar reduz P0
       ...
   ```
3. **Isolamento de Testes Lentos (`@pytest.mark.slow`):**
   - Cálculos geométricos, estruturais e analíticos devem rodar em `< 50 ms`.
   - Simulações completas de voo 6-DOF (`Flight(rocket=..., environment=...)`) devem ser marcadas com `@pytest.mark.slow` quando houver múltiplas varreduras.
4. **Sem Dependências Extras:**
   - Utilize apenas `pytest`, `math` e `numpy` (já presentes no ambiente).
