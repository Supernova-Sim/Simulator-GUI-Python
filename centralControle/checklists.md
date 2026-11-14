# Checklists

## Antes de rodar uma simulação oficial

- [ ] `data/entrada/openmotor/MotorNovo2.ric` é a versão mais recente?
- [ ] `data/entrada/atmosfera/` corresponde à data/local do lançamento?
- [ ] `python centralControle/rodar.py fs` → todos os diagnósticos OK?
- [ ] A geometria do foguete (`configs/foguetes/hefesto/geometria.py`) está atualizada?
- [ ] O JSON anterior de referência está salvo em `data/saida/`?

## Antes de commitar

- [ ] `git status` — só mudanças intencionais?
- [ ] Rodou `rodar.py sim` e o apogeu ainda é coerente com a referência?
- [ ] Rodou `rodar.py fs` e tudo passou?
- [ ] Atualizou este checklist se mudou o fluxo?

## Antes de submeter para a IREC

- [ ] FS carcaça ≥ 2.0
- [ ] FS aletas ≥ 2.0
- [ ] FS estrutura ≥ 2.0
- [ ] FS recuperação ≥ 2.0
- [ ] P0 ≤ 8 MPa
- [ ] Kn ≤ 250
- [ ] mass flux ≤ 1406 kg/(m²·s)
- [ ] Apogeu dentro da faixa alvo da categoria
- [ ] Margem de estabilidade ≥ 1 cal
