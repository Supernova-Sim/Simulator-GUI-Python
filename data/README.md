# `data/` — Taxonomia e Regras

Raiz de trabalho do Hefesto. Separada por **papel** (entrada bruta, catálogo revisado,
execuções e cache), não por tipo de arquivo.

| Diretório | Função | Mutabilidade | Versionamento |
|-----------|--------|--------------|---------------|
| `assets/` | Insumos brutos usados por simuladores: motores (`.ric`, `.eng`), arrasto (`.csv`), atmosfera (`.nc`), `.ork` importados | Semi-estável: escrita apenas por upload/importação explícita, nunca sobrescrita silenciosa | `.ric`/`.eng`/`.csv`/`.ork` versionados; `assets/atmosphere/**/*.nc` fora do Git |
| `catalog/` | Presets JSON tipados que a GUI lista (foguetes, motores, sítios, limites, missões) | Revisado por humano; cada escrita é atômica e explícita | Versionado; IDs são slugs estáveis |
| `runs/` | Snapshots imutáveis de simulações concluídas (`SimulationResult` JSON) | Apenas criação/leitura/exclusão de snapshot | Ignorado no Git (saída de execução) |
| `cache/` | Artefatos derivados: `openrocket/` (parse .ork por sha256) e `motors/` (descoberta de `.ric` por caminho + mtime/sha256) | Descartável e reconstruível a qualquer momento | Ignorado no Git |

## Regras

1. **Golden Master protegido.** `catalog/rockets/hefesto_v1.json` é o baseline físico do
   Hefesto V1: nunca sobrescrever. `tests/golden/hefesto_baseline.json` é o espelho pinado
   das massas/métricas e também não deve ser editado para "fazer o teste passar".
2. **Presets novos, não reescrita.** Ajustes de foguete/motor viram novo ID em `catalog/`
   (`POST` via GUI "Salvar como novo preset"), preservando o preset de origem.
3. **`assets/` é entrada, não cache.** Ferramentas não devem regravar `.ric`/`.eng`/`.csv`;
   uploads passam por validação (extensão, contenção de path, parse do formato).
4. **`cache/` pode ser apagado.** Se removido, o sistema reconstrói na próxima listagem.
   Falha de escrita no cache nunca deve quebrar a listagem de motores.
5. **`runs/` não é fonte de verdade.** É histórico de execução; apagar um snapshot não
   altera presets nem assets.
