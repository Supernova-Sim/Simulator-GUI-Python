Definir casos de teste para validar a fisica e confirmar a coerencia (usando a skill `.agents/skills/validacao-fisica-foguete/SKILL.md`):
- [ ] **Propulsão (`motor.py` / `motorlib_*.py`):** Validar conservação geométrica da massa dos grãos BATES, integral trapezoidal da curva de empuxo ($\int F dt = I_{total}$) e monotonicidade parametrizada ($r_{garganta}$, $r_{core}$, comprimento).
- [ ] **Segurança (`seguranca.py`):** Validar fórmula analítica de tensão circunferencial ($\sigma_\theta = P_0 r / t$) e fronteiras exatas de aprovação/reprovação ($FS$, $P_0$, $K_n$, fluxo de massa).
- [ ] **Coifa (`coifa.py`):** Validar condições de contorno $r(0)=0, r(L)=R$, limite analítico cônico, proporcionalidade linear com `densidade`/`thickness` (CG invariante) e limites geométricos ($0.5 L < CG < L$).
- [ ] **Aletas (`aletas.py` / `aletas_rasaero.py`):** Validar caso limite de aleta retangular sem enflechamento ($A = b \cdot c$, $X_{cg} = c/2$) e conversão exata SI $\leftrightarrow$ polegadas no RASAero.
- [ ] **Componentes e Montagem (`componentes.py` / `modelo.py`):** Validar fórmula analítica de cilindro oco ($I_{zz}, I_{xx}$), Teorema de Steiner com massas pontuais simétricas, invariância sob reordenação da lista de componentes e convenção de eixos RocketPy ($I_{11} = I_{22} \gg I_{33} > 0$).

Mudar o nome de arquivose talvez de funções para quefacilite acompreensão da lógica

Analise de sensibilidade (Morris e Sobol)

Os códigos em scripts precisam ser revisados.

Talvez refatorar após a skill ponytail, pois estaremos com a mentalidade de escrever o necessário.