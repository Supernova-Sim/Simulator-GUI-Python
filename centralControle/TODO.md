Definir casos de teste para validar a física e confirmar a coerência (usando a skill `.agents/skills/validacao-fisica-foguete/SKILL.md`):
- [ ] **Propulsão (`tests/test_motor.py` → `src/motor/derivador.py`, `adaptador_openmotor.py`):** Validar conservação geométrica da massa dos grãos BATES, integral trapezoidal da curva de empuxo ($\int F dt = I_{total}$) e monotonicidade parametrizada ($r_{garganta}$, $r_{core}$, comprimento).
- [ ] **Segurança (`tests/test_motor.py` → `src/motor/seguranca.py`):** Validar fórmula analítica de tensão circunferencial ($\sigma_\theta = P_0 r / t$) e fronteiras exatas de aprovação/reprovação ($FS$, $P_0$, $K_n$, fluxo de massa).
- [ ] **Coifa (`tests/test_estrutura.py` → `src/estrutura/coifa.py`):** Validar condições de contorno $r(0)=0, r(L)=R$, limite analítico cônico, proporcionalidade linear com `densidade`/`thickness` (CG invariante) e limites geométricos ($0.5 L < CG < L$).
- [ ] **Aletas (`tests/test_estrutura.py` → `src/estrutura/aletas.py`):** Validar caso limite de aleta retangular sem enflechamento ($A = b \cdot c$, $X_{cg} = c/2$) e conversão exata SI $\leftrightarrow$ polegadas no RASAero.
- [ ] **Componentes e Montagem (`tests/test_estrutura.py` → `src/estrutura/componentes.py`, `agregador.py`):** Validar fórmula analítica de cilindro oco ($I_{zz}, I_{xx}$), Teorema de Steiner com massas pontuais simétricas, invariância sob reordenação da lista de componentes e convenção de eixos RocketPy ($I_{11} = I_{22} \gg I_{33} > 0$).

Análise de sensibilidade (Morris e Sobol).
