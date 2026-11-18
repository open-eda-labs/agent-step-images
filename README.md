# agent-step-images

Imagem OCI do passo de agente do vuln fixer (nível N2 de P5): Cline CLI, JDK 21, Maven e o `n2-adapter`. Sem credencial de escrita. OpenHands é a segunda opção de harness.

Etapa do plano: P5 (N2). Decisões: D-01, D-09, D-15, D-28, D-42, ADR-0005, ADR-0006. A fonte da verdade é o [Plano Mestre](https://github.com/open-eda-labs/open-eda-labs.github.io/blob/main/docs/PLANO_MESTRE.md).

## Como funciona

O passo `fix` de `agent-workflows` roda nesta imagem (o Dockerfile dele é `FROM` esta) e chama o adaptador como gancho N2, dentro do próprio pod, quando uma subida de versão quebra build ou testes:

```
$N2_HOOK <in> <out>        # N2_HOOK=/opt/n2/n2-adapter
```

1. Copia `<in>/repo` (o repositório que quebrou, já com as versões novas) para um diretório descartável, sem `.git` nem `target`, e faz um commit de base.
2. Põe `workspace/AGENTS.md` na raiz da cópia (instruções do agente, D-15; fora do diff) e monta o prompt com `prompts/n2-migration.v1.md` mais o final de `<in>/error.log`.
3. Roda o Cline headless contra o gateway, com tempo limite e limite de passos, num ambiente sem segredo (nenhuma variável com TOKEN, SECRET, PASSWORD, KEY ou CREDENTIAL no nome) e com o Maven offline (`-o`): o `fix` já baixou tudo para `~/.m2`.
4. Recusa o diff que toca `.github/`, `Dockerfile` ou `*.sh` (a mesma regra do `check_patches` do publish), que muda linha de versão em qualquer `pom.xml`, ou que apaga ou desliga teste.
5. Roda `mvn -B -ntp -q verify` de novo, limpo, na cópia. Só com ele verde grava `<out>/patch.diff`. O `fix` aplica o patch e refaz a prova inteira (parent, lib, service e re-scan).

O agente não decide nada sozinho: o código de saída do Cline é ignorado; o que vale é o verify do adaptador e, depois, a prova do `fix`.

## Ambiente

| Variável | Obrigatória | Padrão | Uso |
| --- | --- | --- | --- |
| `OPENAI_BASE_URL` | sim | | Chat Completions compatível com OpenAI (no cluster, o LiteLLM) |
| `MODEL` | sim | | Nome lógico no gateway (D-09): `fix-n2` |
| `OPENAI_API_KEY` | sim | | Chave do gateway (Secret no cluster). Não chega ao processo do agente como variável |
| `N2_TIMEOUT` | não | 1800 | Segundos do harness. Com o verify (até 1200 s), fica abaixo do `HOOK_TIMEOUT` de 3600 s do `fix` |
| `N2_MAX_STEPS` | não | 30 | Iterações do agente (cada `iteration_start` do stream JSON do Cline) |
| `N2_HARNESS` | não | `cline` | Binário do harness (os testes usam um falso) |
| `MAVEN_ARGS` | não | | Repassada ao Maven do agente e do verify, com `-o` no fim |

`N2_PROMPT` do publish é o nome do arquivo de prompt sem `.md` (`n2-migration.v1`). Mudou o texto do prompt, suba a versão no nome do arquivo e no Workflow.

## Códigos de saída

| Código | Significado |
| --- | --- |
| 0 | `patch.diff` gravado |
| 2 | Uso ou ambiente: argumentos, `<in>/repo`, `<in>/error.log` ou variável obrigatória ausentes |
| 3 | Harness: falha no `auth`, tempo limite ou limite de passos |
| 4 | `mvn verify` vermelho (ou estourou o tempo) depois do agente |
| 5 | O agente não mudou nada |
| 6 | Diff recusado: caminho proibido, versão em `pom.xml`, teste apagado ou desligado |

Para o `fix`, qualquer código diferente de zero é "N2 não resolveu esta unidade": ela volta à versão anterior e a rodada segue.

## Cline CLI verificado

Pacote npm `cline` 3.0.74 (publicado em 2026-10-26), conferido em 2026-11-18 com `--help` do pacote instalado. O pacote traz um binário compilado por plataforma (`@cline/cli-linux-x64` 3.0.74), que roda sem Node. Invocação usada pelo adaptador:

```
cline auth -p openai-compatible -k "$OPENAI_API_KEY" -m "$MODEL" -b "$OPENAI_BASE_URL" --config <dir>
cline -y --json -t <segundos> --config <dir> -c <cópia> "<prompt>"
```

As ferramentas que o Cline expõe ao modelo são `read_files`, `run_commands`, `editor` e `submit_and_exit`, por `tools` em JSON Schema (D-09). Limites conhecidos da 3.0.74: não há flag de máximo de iterações (o adaptador conta `iteration_start` e mata o processo); o `-t` não interrompe um laço de respostas sem ferramenta (o adaptador tem o próprio relógio); o Cline sai com 0 mesmo quando desiste. A telemetria fica desligada por `DISABLE_TELEMETRY=1` e `DO_NOT_TRACK=1`.

## Testes

```
pip install -r requirements-dev.txt
pytest tests                                   # adaptador com harness falso
CLINE_BIN=/caminho/do/cline pytest tests       # mais o Cline de verdade contra um modelo falso (tests/fake_openai.py)
```

O modelo falso devolve uma sequência roteirizada de chamadas de ferramenta (`editor`, `run_commands`, `submit_and_exit`) em SSE. Prova a ligação, não a qualidade do modelo.

## Trocar para OpenHands

Medida do G-P5: só a imagem e um adaptador de até 300 linhas, sem mudança no Workflow nem nos schemas.

1. Neste repositório: um Dockerfile com OpenHands (CLI headless) no lugar do estágio `cline`, mantendo JDK 21, Maven, git, python3 e `/opt/n2`.
2. No `n2-adapter`: reescrever `harness_setup` e `harness_run` (provedor OpenAI-compatível, modelo, chave, execução headless, contagem de passos). Cópia, prompt, recusa, verify e diff não mudam.
3. Em `agent-workflows`: só a linha `FROM` do Dockerfile, para a nova imagem.

O custo medido fica em [docs/exit-cost.md](docs/exit-cost.md).

## Não testado

- A imagem não foi construída: não havia daemon Docker na sessão. Os digests das bases foram lidos do Docker Hub, e o Dockerfile não rodou.
- Só uma tentativa com modelo real (ver `agent-workflows/docs/fix-measurement.md`); a escolha do backend da rota `fix-n2` (ADR-0006) não foi medida.
- O agente roda no mesmo pod do `fix`, sem sandbox: pode ler o que o pod lê, inclusive a config do Cline com a chave do gateway (`shortcut` no adaptador).
- Skills em `.agents/skills/` (D-15): nenhuma ainda.
- CI deste repositório: ainda não existe.
