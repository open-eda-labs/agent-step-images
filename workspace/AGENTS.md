# Instruções para o agente do passo N2 (vuln fixer, open-eda-labs)

Este arquivo é copiado na raiz da cópia de trabalho pelo `n2-adapter` e não entra no diff.

Você está numa cópia descartável de um repositório Maven de demonstração (dados sintéticos). Uma dependência subiu de versão e o build ou os testes quebraram. Sua tarefa é migrar o código para a versão nova.

- Pode mudar: arquivos em `src/` (código Java, recursos, testes cuja API mudou).
- Não pode mudar: versões ou dependências em `pom.xml`, `.github/`, `Dockerfile`, `*.sh`. O adaptador recusa o diff inteiro se isso acontecer.
- Não apague nem desligue teste (`@Disabled`, `@Ignore`, `skipTests`, `maven.test.skip`). O adaptador recusa.
- Maven offline: `mvn -B -ntp -q verify`. Não há rede para baixar dependência nova.
- Não há segredo neste ambiente e você não precisa de nenhum. Não procure credenciais.
- Termine com `submit_and_exit` só depois de ver `mvn -B -ntp -q verify` verde. O adaptador roda o verify de novo e só aceita o patch se passar.
- Mudança mínima: não reformate nem refatore o que o erro não pede.
