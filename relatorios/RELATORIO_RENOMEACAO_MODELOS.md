# Relatório Técnico: Renomeação Semântica dos Módulos Centrais (`modelo` e `modelos`)

**Data:** 02 de Novembro de 2026  
**Projeto:** Hefesto (Módulo de Simulações Estruturais e Voo 6-DOF)  
**Status:** Concluído e Validado (24/24 testes aprovados)

---

## 1. Justificativa da Refatoração

A presença de dois arquivos no mesmo diretório com nomes quase idênticos (`src/modelo.py` vs. `src/modelos.py`):
1. **Quebrava a intuitividade e legibilidade do código:** Era impossível inferir visualmente a responsabilidade de cada arquivo apenas pelo nome (singular vs. plural).
2. **Ambiguidade de domínio:** A palavra *"modelo"* é genérica demais (podendo significar modelo CAD, modelo de dados, modelo matemático ou modelo aerodinâmico).

---

## 2. Nova Nomenclatura Adotada

| Arquivo Antigo | Novo Nome | Papel Arquitetural Exato | Símbolos Principais Exportados |
| :--- | :--- | :--- | :--- |
| `src/modelo.py` | [`src/agregador_estrutural.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/agregador_estrutural.py) | **Cálculo analítico de massa, CG e tensor de inércia** de toda a estrutura seca usando o Teorema de Steiner (eixos paralelos). | `FogueteResolvido`, `resolver()` |
| `src/modelos.py` | [`src/construtor_foguete.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/construtor_foguete.py) | **Builder do simulador RocketPy:** Monta os objetos finais de voo (`SolidMotor`, `Rocket`, aletas, coifa, paraquedas) prontos para a simulação 6-DOF. | `FogueteMontado`, `ModoFoguete`, `build_rocket()`, `build_motor()` |

---

## 3. Arquivos Atualizados no Repositório

Todas as referências foram atualizadas e validadas:

1. [`src/agregador_estrutural.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/agregador_estrutural.py): Atualizado cabeçalho do módulo.
2. [`src/construtor_foguete.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/construtor_foguete.py): Atualizado cabeçalho e import de `src.agregador_estrutural`.
3. [`src/inspecao.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/inspecao.py): Importa `resolver` de `src.agregador_estrutural`.
4. [`scripts/simDeterministica.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/scripts/simDeterministica.py): Importa `ModoFoguete, build_rocket` de `src.construtor_foguete`.
5. [`scripts/varredura.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/scripts/varredura.py): Importa `ModoFoguete, build_rocket` de `src.construtor_foguete`.
6. [`scripts/monteCarloIrec.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/scripts/monteCarloIrec.py): Importa `build_rocket` de `src.construtor_foguete`.
7. [`debug.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/debug.py): Importa `build_rocket` de `src.construtor_foguete`.
8. [`tests/test_calculos_estrutura.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/tests/test_calculos_estrutura.py): Importa `resolver` de `src.agregador_estrutural`.
9. [`tests/test_integracao_voo.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/tests/test_integracao_voo.py): Importa `build_rocket` de `src.construtor_foguete`.
10. [`docs/arquitetura/c2-containers.md`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/docs/arquitetura/c2-containers.md) e [`docs/arquitetura/c3-execucao-voo.md`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/docs/arquitetura/c3-execucao-voo.md): Diagramas arquiteturais sincronizados com os novos nomes.
11. Diagramas C4 Nível 4 regenerados: `src__agregador_estrutural.c4.md` e `src__construtor_foguete.c4.md`.

---

## 4. Validação

* `uv run pytest` ➔ **24/24 testes aprovados** em 2.99s.
* `uv run python centralControle/rodar.py sim --sem-salvar` ➔ Executou nominal com apogeu de 2900.9 m AGL.
* `uv run python debug.py` ➔ Executou com sucesso.
