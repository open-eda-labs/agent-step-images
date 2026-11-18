# Custo de saída do harness do N2 (G-P5)

Métrica do G-P5: trocar Cline CLI por OpenHands custa só a imagem e um adaptador de até 300 linhas, sem mudança no Workflow nem nos schemas.

## Linha de base (Cline CLI 3.0.74, 2026-11-18)

| Peça | Tamanho |
| --- | --- |
| `n2-adapter` inteiro | 179 linhas (152 não vazias) |
| Parte específica do Cline (`harness_setup` e `harness_run`) | 37 linhas não vazias |
| Dockerfile, estágio do harness | 3 linhas (estágio `cline`) mais 1 `COPY` |
| `agent-workflows` | 1 linha (`FROM` do Dockerfile) |

## Troca para OpenHands

Ainda não feita. Ao fazer, registrar aqui: linhas alteradas no `n2-adapter` (`git diff --stat`), no Dockerfile e fora deste repositório (o esperado é só o `FROM` do `agent-workflows`), e o resultado da mesma unidade do N2 com os dois harnesses.
