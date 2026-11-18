Uma subida de versão de dependência (feita antes, fora deste passo) quebrou o build ou os testes deste repositório Maven.
As versões novas já estão no pom.xml e ficam como estão. Migre o código-fonte para elas, até `mvn -B -ntp -q verify` passar.

Regras (também em AGENTS.md):
- Mude só código Java e recursos em src/. Não mude versões nem dependências em nenhum pom.xml.
- Não mexa em .github/, Dockerfile nem scripts .sh.
- Não apague, desligue nem afrouxe teste (@Disabled, @Ignore, skipTests). Teste só muda se a API que ele usa mudou.
- O Maven roda offline: não há dependência nova disponível.
- Rode `mvn -B -ntp -q verify` antes de terminar e só chame submit_and_exit com ele verde.

Log do Maven que falhou (final):

```
{error_log}
```
